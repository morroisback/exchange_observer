import asyncio
import logging
import time

from datetime import datetime, timezone
from typing import Callable, Any

from .price_data_store import PriceDataStore
from .models import Exchange
from .interfaces import IAsyncTask


class ArbitrageEngine(IAsyncTask):
    def __init__(
        self,
        price_data_store: PriceDataStore,
        arbitrage_check_interval_seconds: int = 5,
        min_arbitrage_profit_percent: float = 0.1,
        max_data_age_seconds: int = 10,
        arbitrage_callback: Callable[[dict[str, Any]], None] = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.price_data_store = price_data_store
        self.arbitrage_check_interval_seconds = arbitrage_check_interval_seconds
        self.min_arbitrage_profit_percent = min_arbitrage_profit_percent
        self.max_data_age_seconds = max_data_age_seconds
        self.arbitrage_callback = arbitrage_callback

        self.arbitrage_task: asyncio.Task | None = None
        self.is_running = False

    async def arbitrage_loop(self) -> None:
        while self.is_running:
            start_time = time.time()
            try:
                opportunities_df = self.price_data_store.find_arbitrage_opportunities(
                    min_profit_percent=self.min_arbitrage_profit_percent,
                    max_data_age_seconds=self.max_data_age_seconds,
                )

                if not opportunities_df.empty:
                    for symbol, row in opportunities_df.iterrows():
                        buy_data = self.price_data_store.get_data_for_symbol(Exchange(row["buy_exchange"]), symbol)
                        sell_data = self.price_data_store.get_data_for_symbol(Exchange(row["sell_exchange"]), symbol)

                        buy_bid = buy_data.bid_price if buy_data else "N/A"
                        buy_ask = buy_data.ask_price if buy_data else "N/A"

                        sell_bid = sell_data.bid_price if sell_data else "N/A"
                        sell_ask = sell_data.ask_price if sell_data else "N/A"

                        current_utc_time = datetime.now(timezone.utc)

                        opportunity_details = {
                            "symbol": symbol,
                            "buy_exchange": row["buy_exchange"],
                            "buy_price": row["buy_price"],
                            "buy_bid": buy_bid,
                            "buy_ask": buy_ask,
                            "sell_exchange": row["sell_exchange"],
                            "sell_price": row["sell_price"],
                            "sell_bid": sell_bid,
                            "sell_ask": sell_ask,
                            "profit_percent": row["profit_percent"],
                            "buy_data_age": (current_utc_time - row["last_updated_buy"]).total_seconds(),
                            "sell_data_age": (current_utc_time - row["last_updated_sell"]).total_seconds(),
                        }

                        # self.logger.info(
                        #     f"\nSymbol: {symbol} | "
                        #     f"Buy on {row['buy_exchange']}: Ask={row['buy_price']:.8f} (Bid={buy_bid}, Ask={buy_ask}) | "
                        #     f"Sell on {row['sell_exchange']}: Bid={row['sell_price']:.8f} (Bid={sell_bid}, Ask={sell_ask}) | "
                        #     f"Profit: {row['profit_percent']:.4f}%"
                        #     f" (Buy Data Age: {(current_utc_time - row['last_updated_buy']).total_seconds():.2f}s, "
                        #     f"Sell Data Age: {(current_utc_time - row['last_updated_sell']).total_seconds():.2f}s)"
                        # )

                        if self.arbitrage_callback:
                            self.arbitrage_callback(opportunity_details)

                else:
                    self.logger.info("No arbitrage opportunities found.")

            except Exception as e:
                self.logger.exception(f"Error in arbitrage detection loop: {e}")

            elapsed_time = time.time() - start_time
            await asyncio.sleep(max(0, self.arbitrage_check_interval_seconds - elapsed_time))

    async def start(self) -> None:
        if self.is_running:
            self.logger.info("ArbitrageEngine is already running")
            return

        self.is_running = True
        self.arbitrage_task = asyncio.create_task(self.arbitrage_loop())
        self.logger.info("Arbitrage detection loop started")

    async def stop(self) -> None:
        if not self.is_running:
            self.logger.info("ArbitrageEngine is not running")
            return

        self.is_running = False
        if self.arbitrage_task:
            self.arbitrage_task.cancel()
            try:
                await self.arbitrage_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error while canceling arbitrage task: {e}")
        self.logger.info("Arbitrage detection loop stopped")
