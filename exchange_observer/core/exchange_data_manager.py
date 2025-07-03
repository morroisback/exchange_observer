import asyncio
import logging
import time

from datetime import datetime, timezone

from .interfaces import IExchangeClient
from .models import PriceData, Exchange
from .price_data_store import PriceDataStore

from exchange_observer.exchanges import BinanceClient, BybitClient, GateioClient


class ExchangeDataManager:
    def __init__(
        self,
        exchange_to_monitor: list[Exchange] | None = None,
        arbitrage_check_interval_seconds: int = 5,
        min_arbitrage_profit_percent: float = 0.1,
        max_data_age_seconds: int = 10,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.price_data_store = PriceDataStore()

        self.clients: dict[Exchange, IExchangeClient] = {}
        if exchange_to_monitor is None:
            exchange_to_monitor = [Exchange.BINANCE, Exchange.BYBIT, Exchange.GATEIO]

        for exchange in exchange_to_monitor:
            client = self.create_client(exchange)
            if client:
                self.clients[exchange] = client
            else:
                self.logger.warning(f"Could not create client for {exchange.value}")

        self.arbitrage_check_interval_seconds = arbitrage_check_interval_seconds
        self.min_arbitrage_profit_percent = min_arbitrage_profit_percent
        self.max_data_age_seconds = max_data_age_seconds

        self.arbitrage_task: asyncio.Task | None = None
        self.is_running = False

    def on_price_data_receive(self, data: dict[str, PriceData]) -> None:
        for price_data in data.values():
            self.price_data_store.update_price_data(price_data)

    def on_client_error(self, message: str) -> None:
        self.logger.error(f"Client error: {message}")

    def on_client_connected(self) -> None:
        self.logger.info("Client connected")

    def on_client_disconnected(self) -> None:
        self.logger.info("Client disconnected")

    def create_client(self, exchange: Exchange) -> IExchangeClient | None:
        client_args = [
            self.on_price_data_receive,
            # self.on_client_error,
            # self.on_client_connected,
            # self.on_client_disconnected,
        ]

        if exchange == Exchange.BINANCE:
            return BinanceClient(*client_args)
        elif exchange == Exchange.BYBIT:
            return BybitClient(*client_args)
        elif exchange == Exchange.GATEIO:
            return GateioClient(*client_args)
        else:
            self.logger.error(f"Unsupported exchange type: {exchange}")
            return None

    async def arbitrage_loop(self) -> None:
        while self.is_running:
            start_time = time.time()
            try:
                opportunities_df = self.price_data_store.find_arbitrage_opportunities(
                    min_profit_percent=self.min_arbitrage_profit_percent,
                    max_data_age_seconds=self.max_data_age_seconds,
                )

                if not opportunities_df.empty:
                    self.logger.info("\n--- ARBITRAGE OPPORTUNITIES FOUND ---")

                    for symbol, row in opportunities_df.iterrows():
                        buy_data = self.price_data_store.get_data_for_symbol(Exchange(row["buy_exchange"]), symbol)
                        sell_data = self.price_data_store.get_data_for_symbol(Exchange(row["sell_exchange"]), symbol)

                        buy_bid = buy_data.bid_price if buy_data else "N/A"
                        buy_ask = buy_data.ask_price if buy_data else "N/A"

                        sell_bid = sell_data.bid_price if sell_data else "N/A"
                        sell_ask = sell_data.ask_price if sell_data else "N/A"

                        current_utc_time = datetime.now(timezone.utc)

                        self.logger.info(
                            f"\nSymbol: {symbol} | "
                            f"Buy on {row["buy_exchange"]}: Ask={row["buy_price"]:.8f} (Bid={buy_bid}, Ask={buy_ask}) | "
                            f"Sell on {row["sell_exchange"]}: Bid={row["sell_price"]:.8f} (Bid={sell_bid}, Ask={sell_ask}) | "
                            f"Profit: {row["profit_percent"]:.4f}%"
                            f" (Buy Data Age: {(current_utc_time - row["last_updated_buy"]).total_seconds():.2f}s, "
                            f"Sell Data Age: {(current_utc_time - row["last_updated_sell"]).total_seconds():.2f}s)"
                        )
                else:
                    self.logger.info("No arbitrage opportunities found.")

            except Exception as e:
                self.logger.exception(f"Error in arbitrage detection loop: {e}")

            elapsed_time = time.time() - start_time
            await asyncio.sleep(max(0, self.arbitrage_check_interval_seconds - elapsed_time))

    async def start(self) -> None:
        if self.is_running:
            self.logger.info("ExchangeDataManager is already running")
            return

        self.is_running = True
        self.logger.info("Starting ExchangeDataManager...")

        client_start_tasks = [client.start() for client in self.clients.values()]
        await asyncio.gather(*client_start_tasks)
        self.logger.info("All exchange clients initialized and running")

        self.arbitrage_task = asyncio.create_task(self.arbitrage_loop())
        self.logger.info("Arbitrage detection loop started")

    async def stop(self) -> None:
        if not self.is_running:
            self.logger.info("ExchangeDataManager is not running")
            return

        self.is_running = False
        self.logger.info("Stopping ExchangeDataManager...")

        client_stop_tasks = [client.stop() for client in self.clients.values()]
        await asyncio.gather(*client_stop_tasks)
        self.logger.info("All exchange clients stopped")

        if self.arbitrage_task:
            self.arbitrage_task.cancel()
            try:
                await self.arbitrage_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error while canceling arbitrage task: {e}")

        self.logger.info("ExchangeDataManager stopped")
