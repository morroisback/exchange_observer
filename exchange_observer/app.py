import logging

from typing import Callable

from .core import (
    ArbitrageEngine,
    ExchangeDataManager,
    PriceDataStore,
    Exchange,
    ArbitrageOpportunity,
)
from .core.interfaces import IAsyncTask
from .exchanges import ExchangeClientFactory


class ExchangeObserverApp(IAsyncTask):
    def __init__(
        self,
        exchanges_to_monitor: list[Exchange],
        arbitrage_check_interval_seconds: int = 5,
        min_arbitrage_profit_percent: float = 0.1,
        max_data_age_seconds: int = 10,
        arbitrage_callback: Callable[[list[ArbitrageOpportunity]], None] = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchanges_to_monitor = exchanges_to_monitor
        self.arbitrage_check_interval_seconds = arbitrage_check_interval_seconds
        self.min_arbitrage_profit_percent = min_arbitrage_profit_percent
        self.max_data_age_seconds = max_data_age_seconds
        self.arbitrage_callback = arbitrage_callback

        self.data_manager = ExchangeDataManager()
        self.client_factory = ExchangeClientFactory(listener=self.data_manager)
        self.clients = {
            exchange.value: self.client_factory.create_client(exchange) for exchange in self.exchanges_to_monitor
        }
        self.clients = {name: client for name, client in self.clients.items() if client is not None}

        self.price_data_store = PriceDataStore()
        self.arbitrage_engine = ArbitrageEngine(
            price_data_store=self.price_data_store,
            arbitrage_check_interval_seconds=self.arbitrage_check_interval_seconds,
            min_arbitrage_profit_percent=self.min_arbitrage_profit_percent,
            max_data_age_seconds=self.max_data_age_seconds,
            arbitrage_callback=self.arbitrage_callback,
        )

        self.data_manager.configure(
            clients=self.clients, price_data_store=self.price_data_store, arbitrage_engine=self.arbitrage_engine
        )

    async def start(self) -> None:
        self.logger.info("Starting ExchangeObserverApp...")
        await self.data_manager.start()
        self.logger.info("ExchangeObserverApp started.")

    async def stop(self) -> None:
        self.logger.info("Stopping ExchangeObserverApp...")
        await self.data_manager.stop()
        self.logger.info("ExchangeObserverApp stopped.")
