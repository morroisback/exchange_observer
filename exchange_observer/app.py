import logging
from typing import Callable, Any

from .core import ArbitrageEngine, ExchangeDataManager, PriceDataStore, Exchange
from .exchanges import ExchangeClientFactory


class ExchangeObserverApp:
    def __init__(
        self,
        exchanges_to_monitor: list[Exchange],
        min_arbitrage_profit_percent: float,
        arbitrage_callback: Callable[[dict[str, Any]], None] = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchanges_to_monitor = exchanges_to_monitor
        self.min_arbitrage_profit_percent = min_arbitrage_profit_percent
        self.arbitrage_callback = arbitrage_callback

        self.price_data_store = PriceDataStore()
        self.data_manager = ExchangeDataManager(self.price_data_store)
        self.client_factory = ExchangeClientFactory(listener=self.data_manager)

        self.clients = {
            exchange.value: self.client_factory.create_client(exchange) for exchange in self.exchanges_to_monitor
        }
        self.clients = {name: client for name, client in self.clients.items() if client is not None}

        self.arbitrage_engine = ArbitrageEngine(
            price_data_store=self.price_data_store,
            min_arbitrage_profit_percent=self.min_arbitrage_profit_percent,
            arbitrage_callback=self.arbitrage_callback,
        )

        self.data_manager.clients = self.clients
        self.data_manager.arbitrage_engine = self.arbitrage_engine

    async def start(self):
        self.logger.info("Starting ExchangeObserverApp...")
        await self.data_manager.start()
        self.logger.info("ExchangeObserverApp started.")

    async def stop(self):
        self.logger.info("Stopping ExchangeObserverApp...")
        await self.data_manager.stop()
        self.logger.info("ExchangeObserverApp stopped.")
