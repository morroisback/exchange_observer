import asyncio
import logging
import websockets

from abc import abstractmethod
from typing import Any, Callable

from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, InvalidURI, WebSocketException

from exchange_observer.core.interfaces import IExchangeClient
from exchange_observer.core.models import PriceData, Exchange


class BaseExchangeClient(IExchangeClient):
    RECONNECT_MAX_DELAY_SECONDS = 60
    RECONNECT_MAX_ATTEMPTS_PER_SESSION = 5

    def __init__(
        self,
        on_data_callback: Callable[[dict[str, PriceData]], None] | None = None,
        on_error_callback: Callable[[str], None] | None = None,
        on_connected_callback: Callable[[], None] | None = None,
        on_disconnected_callback: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback
        self.on_connected_callback = on_connected_callback
        self.on_disconnected_callback = on_disconnected_callback

        self.logger = logging.getLogger(self.__class__.__name__)

        self.reconnect_attempt = 0

        self.websocket: websockets.ClientConnection | None = None
        self.websocket_task: asyncio.Task | None = None
        self.is_running = False

        self.data: dict[str, PriceData] = {}
        self.websocket_url: str = ""
        self.exchange: Exchange = Exchange.NONE

    async def async_callback(self, callback: Callable, *args: Any, **kwargs: Any) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                # loop = asyncio.get_event_loop()
                # await loop.run_in_executor(None, callback, *args, **kwargs)
                callback(*args, **kwargs)

        except Exception as e:
            self.logger.error(f"Error in callback function {callback.__name__}: {e}")

    def call_data_callback(self, data: dict[str, PriceData]) -> None:
        if self.on_data_callback:
            asyncio.create_task(self.async_callback(self.on_data_callback, data))

    def call_error_callback(self, message: str) -> None:
        if self.on_error_callback:
            asyncio.create_task(self.async_callback(self.on_error_callback, message))

    def call_connected_callback(self) -> None:
        if self.on_connected_callback:
            asyncio.create_task(self.async_callback(self.on_connected_callback))

    def call_disconnected_callback(self) -> None:
        if self.on_disconnected_callback:
            asyncio.create_task(self.async_callback(self.on_disconnected_callback))

    @abstractmethod
    async def fetch_symbols(self) -> list[str]:
        pass

    @abstractmethod
    async def subscribe_symbols(self, symbols: list[str]) -> None:
        pass

    @abstractmethod
    def process_message(self, message: str) -> None:
        pass

    async def apply_reconnect_delay(self) -> None:
        self.reconnect_attempt += 1
        delay = min(2**self.reconnect_attempt, self.RECONNECT_MAX_DELAY_SECONDS)
        self.logger.warning(f"Retrying connection in {delay:.2f} seconds (attempt {self.reconnect_attempt}).")
        await asyncio.sleep(delay)

    async def connect_and_subscribe(self) -> None:
        self.websocket = None

        try:
            # async with websockets.connect(self.websocket_url, ping_interval=20, ping_timeout=10) as ws:
            async with websockets.connect(self.websocket_url) as ws:
                self.websocket = ws
                self.logger.info("WebSocket connected")
                self.call_connected_callback()
                self.reconnect_attempt = 0

                symbols = await self.fetch_symbols()
                if not symbols:
                    self.logger.error("No symbols to subscribe")
                    self.call_error_callback("No symbols to subscribe")
                    self.is_running = False
                    return

                await self.subscribe_symbols(symbols)
                await self.receive_message()
                self.logger.info("Message reception loop ended for current connection")

        except asyncio.TimeoutError:
            pass
        except (InvalidURI, WebSocketException, ConnectionRefusedError, OSError) as e:
            self.logger.error(f"Connection/Subscription error: {e}")
            self.call_error_callback(f"Connection/Subscription error: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error during connection/subscription: {e}")
            self.call_error_callback(f"Unexpected error during connection/subscription: {e}")
        finally:
            self.websocket = None

    async def receive_message(self) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for receive message")
            return

        while self.is_running and self.websocket:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                self.process_message(message)
            except asyncio.TimeoutError:
                continue
            except ConnectionClosedOK:
                self.logger.info("WebSocket connection closed")
                break
            except ConnectionClosed as e:
                self.logger.error(f"WebSocket connection closed with error: {e}")
                self.call_error_callback(f"WebSocket connection closed with error: {e}")
                break
            except Exception as e:
                self.logger.exception(f"Unexpected error during receiving/processing message: {e}")
                self.call_error_callback(f"Unexpected error during receiving/processing message: {e}")
                break

    async def websocket_loop(self) -> None:
        while self.is_running and self.reconnect_attempt <= self.RECONNECT_MAX_ATTEMPTS_PER_SESSION:
            await self.connect_and_subscribe()

            if self.is_running:
                await self.apply_reconnect_delay()

        if self.reconnect_attempt > self.RECONNECT_MAX_ATTEMPTS_PER_SESSION:
            self.logger.critical(f"Failed to reconnect after {self.RECONNECT_MAX_ATTEMPTS_PER_SESSION} attempts")
            self.call_error_callback(f"Failed to reconnect after {self.RECONNECT_MAX_ATTEMPTS_PER_SESSION} attempts")

        self.is_running = False
        self.logger.info("WebSocket loop terminated")
        self.call_disconnected_callback()

    async def start(self) -> None:
        if self.is_running:
            self.logger.info("Client is already running")
            return

        self.logger.info("Starting client...")
        self.is_running = True
        self.reconnect_attempt = 0
        self.websocket_task = asyncio.create_task(self.websocket_loop())

    async def stop(self) -> None:
        if not self.is_running:
            self.logger.info("Client is not running")
            return

        self.logger.info("Stopping client...")
        self.is_running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                self.logger.warning(f"Error closing WebSocket: {e}")

        if self.websocket_task and not self.websocket_task.done():
            try:
                await asyncio.wait_for(self.websocket_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("WebSocket task did not terminate within timeout")
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error while canceling websocket task: {e}")

            except Exception as e:
                self.logger.error(f"Error waiting for websocket task to stop: {e}")

        self.logger.info("Client stopped")

    def get_data(self, symbol: str | None = None) -> dict[str, PriceData] | PriceData | None:
        if symbol:
            return self.data.get(symbol)
        return self.data
