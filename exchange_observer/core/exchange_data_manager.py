import asyncio
import logging

from typing import Callable

from .arbitrage_engine import ArbitrageEngine
from .interfaces import IExchangeClientListener, IAsyncTask
from .models import PriceData, Exchange
from .price_data_store import PriceDataStore


class ExchangeDataManager(IExchangeClientListener, IAsyncTask):
    def __init__(
        self,
        connected_callback: Callable[[Exchange], None] = None,
        disconnected_callback: Callable[[Exchange], None] = None,
        error_callback: Callable[[Exchange, str], None] = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        self.connected_callback = connected_callback
        self.disconnected_callback = disconnected_callback
        self.error_callback = error_callback

        self.clients: dict[str, IAsyncTask] = {}
        self.price_data_store: PriceDataStore | None = None
        self.arbitrage_engine: ArbitrageEngine | None = None

        self.is_configured = False
        self.is_running = False

    def configure(
        self, clients: dict[str, IAsyncTask], price_data_store: PriceDataStore, arbitrage_engine: ArbitrageEngine
    ) -> None:
        self.clients = clients
        self.price_data_store = price_data_store
        self.arbitrage_engine = arbitrage_engine

        self.is_configured = True

    def on_data_received(self, data: PriceData) -> None:
        self.price_data_store.update_price_data(data)

    def on_error(self, exchange: Exchange, message: str) -> None:
        self.logger.error(f"Client error: {message}")
        if self.error_callback:
            self.error_callback(exchange, message)

    def on_connected(self, exchange: Exchange) -> None:
        self.logger.info("Client connected")
        if self.connected_callback:
            self.connected_callback(exchange)

    def on_disconnected(self, exchange: Exchange) -> None:
        self.logger.info("Client disconnected")
        if self.disconnected_callback:
            self.disconnected_callback(exchange)

    async def start(self) -> None:
        if not self.is_configured:
            self.logger.error("Cannot start: not configured")
            return

        if self.is_running:
            self.logger.info("ExchangeDataManager is already running")
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
