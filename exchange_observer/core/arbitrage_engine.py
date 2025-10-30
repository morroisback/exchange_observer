import asyncio
import logging
import time

from typing import Callable

from .price_data_store import PriceDataStore
from .interfaces import IAsyncTask
from .models import ArbitrageOpportunity


class ArbitrageEngine(IAsyncTask):
    def __init__(
        self,
        price_data_store: PriceDataStore,
        arbitrage_check_interval_seconds: int = 5,
        min_arbitrage_profit_percent: float = 0.1,
        max_data_age_seconds: int = 10,
        arbitrage_callback: Callable[[list[ArbitrageOpportunity]], None] = None,
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
                opportunities = self.price_data_store.find_arbitrage_opportunities(
                    min_profit_percent=self.min_arbitrage_profit_percent,
                    max_data_age_seconds=self.max_data_age_seconds,
                )

                if opportunities and self.arbitrage_callback:
                        self.arbitrage_callback(opportunities)

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
