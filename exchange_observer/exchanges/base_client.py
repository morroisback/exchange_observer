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
    PING_INTERVAL_SECONDS = 20

    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__()
        self.listener = listener
        self.logger = logging.getLogger(self.__class__.__name__)

        self.reconnect_attempt = 0

        self.websocket: websockets.ClientConnection | None = None
        self.websocket_task: asyncio.Task | None = None
        self.ping_task: asyncio.Task | None = None
        self.is_running = False

        self.data: dict[str, PriceData] = {}
        self.websocket_url: str = ""
        self.exchange: Exchange = Exchange.NONE

    async def async_callback(self, callback: Callable, *args: Any, **kwargs: Any) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
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
    def is_ping_message(self, message: str) -> bool:
        pass

    @abstractmethod
    def is_pong_message(self, message: str) -> bool:
        pass

    @abstractmethod
    async def fetch_symbols(self) -> list[str]:
        pass

    @abstractmethod
    async def subscribe_symbols(self, symbols: list[str]) -> None:
        pass

    @abstractmethod
    async def send_ping(self) -> None:
        pass

    @abstractmethod
    async def handle_ping(self, message: str) -> None:
        pass

    @abstractmethod
    async def handle_pong(self, message: str) -> None:
        pass

    @abstractmethod
    async def handle_message(self, message: str) -> None:
        pass

    async def ping_loop(self) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for ping")
            return

        while self.is_running and self.websocket:
            try:
                await self.send_ping()
                await asyncio.sleep(self.PING_INTERVAL_SECONDS)
            except ConnectionClosedOK:
                self.logger.info("WebSocket connection closed during ping")
                break
            except ConnectionClosed as e:
                self.logger.error(f"WebSocket connection closed during ping with error: {e}")
                self.notify_listener("on_error", f"WebSocket connection closed during ping with error: {e}")
                break
            except Exception as e:
                self.logger.exception(f"Unexpected error during ping: {e}")
                self.notify_listener("on_error", f"Unexpected error during ping: {e}")
                break

    async def handle_message_loop(self) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for handle message")
            return

        while self.is_running and self.websocket:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=25.0)
                if self.is_ping_message(message):
                    await self.handle_ping(message)
                elif self.is_pong_message(message):
                    await self.handle_pong(message)
                else:
                    await self.handle_message(message)
            except asyncio.TimeoutError:
                continue
            except ConnectionClosedOK:
                self.logger.info("WebSocket connection closed during handle message")
                break
            except ConnectionClosed as e:
                self.logger.error(f"WebSocket connection closed during handle message with error: {e}")
                self.notify_listener("on_error", f"WebSocket connection closed during handle message with error: {e}")
                break
            except Exception as e:
                self.logger.exception(f"Unexpected error during handle message: {e}")
                self.notify_listener("on_error", f"Unexpected error during handle message: {e}")
                break

    async def apply_reconnect_delay(self) -> None:
        self.reconnect_attempt += 1
        delay = min(2**self.reconnect_attempt, self.RECONNECT_MAX_DELAY_SECONDS)
        self.logger.warning(f"Retrying connection in {delay:.2f} seconds (attempt {self.reconnect_attempt})")
        await asyncio.sleep(delay)

    async def run_websocket_session(self) -> None:
        self.websocket = None
        try:
            async with websockets.connect(self.websocket_url, ping_interval=None, ping_timeout=None) as ws:
                self.websocket = ws
                self.logger.info("WebSocket connected")
                self.notify_listener("on_connected")
                self.reconnect_attempt = 0

                self.ping_task = asyncio.create_task(self.ping_loop())

                symbols = await self.fetch_symbols()
                if not symbols:
                    self.logger.error("No symbols to subscribe")
                    self.notify_listener("on_error", "No symbols to subscribe")
                    return

                await self.subscribe_symbols(symbols)
                await self.handle_message_loop()
                self.logger.info("Websocket session end for current connection")

        except asyncio.TimeoutError:
            pass
        except (InvalidURI, WebSocketException, ConnectionRefusedError, OSError) as e:
            self.logger.error(f"Websocket session error: {e}")
            self.notify_listener("on_error", f"Websocket session  error: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error during websocket session : {e}")
            self.notify_listener("on_error", f"Unexpected error during websocket session : {e}")
        finally:
            if self.ping_task and not self.ping_task.done():
                self.ping_task.cancel()
            self.ping_task = None
            self.websocket = None

    async def websocket_loop(self) -> None:
        while self.is_running:
            await self.run_websocket_session()

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
        self.ping_task = None
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

        if self.ping_task and not self.ping_task.done():
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error while canceling ping task: {e}")

        if self.websocket_task and not self.websocket_task.done():
            self.websocket_task.cancel()
            try:
                await self.websocket_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error while canceling websocket task: {e}")

        self.ping_task = None
        self.websocket_task = None
        self.websocket = None
        self.logger.info("Client stopped")
