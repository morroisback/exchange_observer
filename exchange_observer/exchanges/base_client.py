import asyncio
import logging
import websockets

from abc import abstractmethod
from typing import Any, Callable

from exchange_observer.core import IExchangeClient
from exchange_observer.core import PriceData


class BaseExchangeClient(IExchangeClient):
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

        self.websocket: websockets.ClientConnection | None = None
        self.data: dict[str, PriceData] = {}
        self.symbols: dict[str, dict[str, str]] = []
        self.is_running = False
        self.websocket_task: asyncio.Task | None = None
        self.websocket_url: str = ""

    async def async_callback(self, callback: Callable, *args: Any, **kwargs: Any) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, callback, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error in callback function {callback.__name__}: {e}")

    def call_date_callback(self, data: dict[str, PriceData]) -> None:
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
    async def fetch_symbols(self) -> dict[str, dict[str, str]]:
        pass

    @abstractmethod
    async def subscribe_symbols(self) -> None:
        pass

    @abstractmethod
    def process_message(self, message: str) -> None:
        pass

    async def websocket_loop(self) -> None:
        try:
            async with websockets.connect(self.websocket_url, ping_interval=20, ping_timeout=10) as ws:
                self.websocket = ws
                self.logger.info(f"{self.__class__.__name__} WebSocket connected")
                self.call_connected_callback()

                self.symbols = await self.fetch_symbols()
                if not self.symbols:
                    self.logger.warning("No symbols to subscribe, closing WebSocket")
                    return

                for symbol, symbol_info in self.symbols.items():
                    if symbol not in self.data:
                        self.data[symbol] = PriceData(
                            symbol=symbol,
                            base_coin=symbol_info.get("base_coin"),
                            quote_coin=symbol_info.get("quote_coin")
                        )

                await self.subscribe_symbols()

                while self.is_running:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        self.process_message(message)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosedOK:
                        self.logger.info("WebSocket connection closed")
                        break
                    except websockets.exceptions.ConnectionClosed as e:
                        self.logger.error(f"WebSocket connection closed with error: {e}")
                        self.call_error_callback(f"WebSocket connection closed with error: {e}")
                        break
                    except Exception as e:
                        self.logger.exception(f"Error receiving/processing WebSocket message: {e}")
                        self.call_error_callback(f"Error receiving/processing WebSocket message: {e}")
                        break

        except websockets.exceptions.InvalidURI as e:
            self.logger.error(f"Invalid WebSocket URI: {e}")
            self.call_error_callback(f"Invalid WebSocket URI: {e}")
        except ConnectionRefusedError:
            self.logger.error("Connection refused. Bybit server might be down or firewall blocking")
            self.call_error_callback("Connection refused. Bybit server might be down or firewall blocking")
        except Exception as e:
            self.logger.exception(f"Unexpected error in WebSocket loop: {e}")
            self.call_error_callback(f"Unexpected error in WebSocket loop: {e}")
        finally:
            self.websocket = None
            self.is_running = False
            self.logger.info(f"{self.__class__.__name__} WebSocket loop terminated")
            self.call_disconnected_callback()

    async def start(self) -> None:
        if self.is_running:
            self.logger.info(f"{self.__class__.__name__} client is already running")
            return

        self.logger.info(f"Starting {self.__class__.__name__} client...")
        self.is_running = True
        self.websocket_task = asyncio.create_task(self.websocket_loop())

    async def stop(self) -> None:
        if not self.is_running:
            self.logger.info(f"{self.__class__.__name__} client is not running")
            return

        self.logger.info(f"Stopping {self.__class__.__name__} client...")
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
                self.logger.error(f"Error waiting for websocket task to stop: {e}")

        self.logger.info(f"{self.__class__.__name__} client stopped")

    def get_data(self, symbol: str | None = None) -> dict[str, PriceData] | PriceData | None:
        if symbol:
            return self.data.get(symbol)
        return self.data
