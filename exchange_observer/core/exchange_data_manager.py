import asyncio
import logging

from .arbitrage_engine import ArbitrageEngine
from .interfaces import IExchangeClient, IExchangeClientListener
from .models import PriceData
from .price_data_store import PriceDataStore


class ExchangeDataManager(IExchangeClientListener):
    def __init__(self, price_data_store: PriceDataStore):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.price_data_store = price_data_store

        self.clients: dict[str, IExchangeClient] = {}
        self.arbitrage_engine: ArbitrageEngine | None = None

        self.is_running = False

    def on_data_received(self, data: PriceData) -> None:
        self.price_data_store.update_price_data(data)

    def on_error(self, message: str) -> None:
        self.logger.error(f"Client error: {message}")

    def on_connected(self) -> None:
        self.logger.info("Client connected")

    def on_disconnected(self) -> None:
        self.logger.info("Client disconnected")

    async def start(self) -> None:
        if self.is_running:
            self.logger.info("ExchangeDataManager is already running")
            return

        if not (self.clients and self.arbitrage_engine):
            self.logger.error("Cannot start: clients or arbitrage engine not set")
            return

        self.is_running = True
        self.logger.info("Starting ExchangeDataManager...")

        client_start_tasks = [client.start() for client in self.clients.values()]
        await asyncio.gather(*client_start_tasks)
        self.logger.info("All exchange clients initialized and running")

        await self.arbitrage_engine.start()
        self.logger.info("Arbitrage engine started")

    async def stop(self) -> None:
        if not self.is_running:
            self.logger.info("ExchangeDataManager is not running")
            return

        self.is_running = False
        self.logger.info("Stopping ExchangeDataManager...")

        if self.arbitrage_engine:
            await self.arbitrage_engine.stop()
            self.logger.info("Arbitrage engine stopped")

        client_stop_tasks = [client.stop() for client in self.clients.values()]
        await asyncio.gather(*client_stop_tasks)
        self.logger.info("All exchange clients stopped")

        self.logger.info("ExchangeDataManager stopped")
