import asyncio
import logging
import websockets

from abc import abstractmethod
from typing import Any, Callable

from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, InvalidURI, WebSocketException

from exchange_observer.core import PriceData, Exchange, IExchangeClient, IExchangeClientListener


class BaseExchangeClient(IExchangeClient):
    RECONNECT_MAX_DELAY_SECONDS = 120
    RECONNECT_MAX_ATTEMPTS_PER_SESSION = 5

    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__()
        self.listener = listener
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

    def notify_listener(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        if not self.listener:
            return

        try:
            method = getattr(self.listener, method_name)
            if method:
                asyncio.create_task(self.async_callback(method, *args, **kwargs))
        except Exception as e:
            self.logger.error(f"Error notifying listener method {method_name}: {e}")

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
            async with websockets.connect(self.websocket_url, ping_interval=60, ping_timeout=60) as ws:
                self.websocket = ws
                self.logger.info("WebSocket connected")
                self.notify_listener("on_connected")
                self.reconnect_attempt = 0

                symbols = await self.fetch_symbols()
                if not symbols:
                    self.logger.error("No symbols to subscribe")
                    self.notify_listener("on_error", "No symbols to subscribe")
                    return

                await self.subscribe_symbols(symbols)
                await self.receive_message()
                self.logger.info("Message reception loop ended for current connection")

        except asyncio.TimeoutError:
            pass
        except (InvalidURI, WebSocketException, ConnectionRefusedError, OSError) as e:
            self.logger.error(f"Connection/Subscription error: {e}")
            self.notify_listener("on_error", f"Connection/Subscription error: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error during connection/subscription: {e}")
            self.notify_listener("on_error", f"Unexpected error during connection/subscription: {e}")
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
                self.notify_listener("on_error", f"WebSocket connection closed with error: {e}")
                break
            except Exception as e:
                self.logger.exception(f"Unexpected error during receiving/processing message: {e}")
                self.notify_listener("on_error", f"Unexpected error during receiving/processing message: {e}")
                break

    async def websocket_loop(self) -> None:
        while self.is_running:  # and self.reconnect_attempt <= self.RECONNECT_MAX_ATTEMPTS_PER_SESSION:
            await self.connect_and_subscribe()

            if self.is_running:
                self.notify_listener("on_disconnected")
                await self.apply_reconnect_delay()

        if self.reconnect_attempt > self.RECONNECT_MAX_ATTEMPTS_PER_SESSION:
            self.logger.critical(f"Failed to reconnect after {self.RECONNECT_MAX_ATTEMPTS_PER_SESSION} attempts")
            self.notify_listener(
                "on_error", f"Failed to reconnect after {self.RECONNECT_MAX_ATTEMPTS_PER_SESSION} attempts"
            )

        self.is_running = False
        self.logger.info("WebSocket loop terminated")
        self.notify_listener("on_disconnected")

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
