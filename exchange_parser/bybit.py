import asyncio
import aiohttp
import json
import logging
import websockets

from typing import Any, Callable


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


WEB_BYBIT_SPOT_PUBLIC = "wss://stream.bybit.com/v5/public/spot"
REST_BYBIT_SPOT_INFO = "https://api.bybit.com/v5/market/instruments-info?category=spot"


class Bybit:
    def __init__(
        self,
        on_data_callback: Callable[[dict], None] | None = None,
        on_error_callback: Callable[[str], None] | None = None,
        on_connected_callback: Callable[[], None] | None = None,
        on_disconnected_callback: Callable[[], None] | None = None,
    ) -> None:
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback
        self.on_connected_callback = on_connected_callback
        self.on_disconnected_callback = on_disconnected_callback

        self.websocket = None
        self.data = {}
        self.symbols = []
        self.is_running = False
        self.websocket_task = None
        self.subscription_task = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def async_callback(self, callback: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, callback, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error in callback function {callback.__name__}: {e}")

    def call_date_callback(self, data: dict) -> None:
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

    async def fetch_symbols(self) -> list:
        self.logger.info("Fetching symbols from REST API...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REST_BYBIT_SPOT_INFO) as response:
                    response.raise_for_status()
                    data = await response.json()

                    symbols_list = data.get("result", {}).get("list", {})
                    if not symbols_list:
                        self.logger.warning("No symbols found or API response format changed")
                        self.call_error_callback("No symbols found or API response format changed")
                        return []

                    active_symbols = [
                        symbol.get("symbol")
                        for symbol in symbols_list
                        if symbol.get("status") == "Trading" and symbol.get("symbol")
                    ]

                    self.logger.info(f"Found {len(active_symbols)} active symbols")
                    return active_symbols
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching symbols: {e}")
            self.call_error_callback(f"HTTP error fetching symbols: {e}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error fetching symbols: {e}")
            self.call_error_callback(f"JSON decode error fetching symbols: {e}")
            return []
        except Exception as e:
            self.logger.exception(f"Unexpected error fetching symbols: {e}")
            self.call_error_callback(f"Unexpected error fetching symbols: {e}")
            return []

    async def subscribe_to_symbols(self) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for subscription")
            return

        subscribe_args = []
        for symbol_name in self.symbols:
            subscribe_args.append(f"tickers.{symbol_name}")
            subscribe_args.append(f"orderbook.1.{symbol_name}")

        MAX_ARGS_PER_MESSAGE = 10

        for i in range(0, len(subscribe_args), MAX_ARGS_PER_MESSAGE):
            chunk = subscribe_args[i : i + MAX_ARGS_PER_MESSAGE]
            subscribe_message = json.dumps({"op": "subscribe", "args": chunk})

            try:
                await self.websocket.send(subscribe_message)
                self.logger.info(f"Sent subscribe for {len(chunk)} topics in chunk {i // MAX_ARGS_PER_MESSAGE + 1}")
                # await asyncio.sleep(0.05)
            except Exception as e:
                self.logger.error(f"Error sending subscription chunk {i // MAX_ARGS_PER_MESSAGE + 1}: {e}")
                self.call_error_callback(f"Error sending subscription chunk {i // MAX_ARGS_PER_MESSAGE + 1}: {e}")
                break

    def process_message(self, message: str) -> None:
        try:
            message_data = json.loads(message)
            if "success" in message_data:
                if not message_data["success"]:
                    self.logger.warning(f"Bybit API error: {message_data.get('ret_msg', '')}")
                    self.call_error_callback(f"Bybit API error: {message_data.get('ret_msg', '')}")
                return

            if "topic" in message_data and "data" in message_data:
                symbol = ""
                symbol_price_data = {}

                if "tickers" in message_data["topic"]:
                    symbol = message_data["data"].get("symbol")
                    symbol_price_data = {"last_price": message_data["data"].get("lastPrice")}
                elif "b" in message_data["data"] and "a" in message_data["data"]:
                    symbol = message_data["data"].get("s")
                    bids = message_data["data"]["b"]
                    asks = message_data["data"]["a"]

                    if bids and len(bids) > 0:
                        symbol_price_data["bid_price"] = bids[0][0]
                        symbol_price_data["bid_quantity"] = bids[0][1]
                    if asks and len(asks) > 0:
                        symbol_price_data["ask_price"] = asks[0][0]
                        symbol_price_data["ask_quantity"] = asks[0][1]

                if symbol and symbol_price_data:
                    if symbol not in self.data:
                        self.data[symbol] = {}
                    self.data[symbol].update(symbol_price_data)
                    self.call_date_callback({symbol: self.data[symbol]})
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error processing message: {e}")
            self.call_error_callback(f"JSON decode error processing message: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing message: {e}")
            self.call_error_callback(f"Unexpected error processing message: {e}")

    async def websocket_loop(self) -> None:
        try:
            async with websockets.connect(WEB_BYBIT_SPOT_PUBLIC, ping_interval=20, ping_timeout=10) as ws:
                self.websocket = ws
                self.logger.info("Bybit WebSocket connected")
                self.call_connected_callback()

                self.symbols = await self.fetch_symbols()
                if not self.symbols:
                    self.logger.warning("No symbols to subscribe, closing WebSocket")
                    return

                await self.subscribe_to_symbols()

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

        except websockets.exceptions.ConnectionClosedOK:
            self.logger.info("WebSocket connection closed cleanly outside the loop")
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
            self.logger.info("Bybit WebSocket loop terminated")
            self.call_disconnected_callback()

    def start(self) -> None:
        if self.is_running:
            self.logger.info("Bybit client is already running")
            return

        self.logger.info("Starting Bybit client...")
        self.is_running = True
        self.websocket_task = asyncio.create_task(self.websocket_loop())

    async def stop(self) -> None:
        if not self.is_running:
            self.logger.info("Bybit client is not running")
            return

        self.logger.info("Stopping Bybit client...")
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

        self.logger.info("Bybit client stopped")

    def get_data(self, symbol: str | None = None) -> dict:
        if symbol:
            return self.data.get(symbol)
        return self.data


async def main() -> None:
    def handle_data(data: dict) -> None:
        for s, d in data.items():
            print(f"Received data for {s}: {d.get('last_price')}")

    def handle_error(msg: str) -> None:
        print(f"Error: {msg}")

    def handle_connected() -> None:
        print("Bybit client connected!")

    def handle_disconnected() -> None:
        print("Bybit client disconnected!")

    bybit_client = Bybit(
        on_data_callback=handle_data,
        on_error_callback=handle_error,
        on_connected_callback=handle_connected,
        on_disconnected_callback=handle_disconnected
    )
    bybit_client.start()
    print("Bybit client started. Waiting for data...")

    try:
        await asyncio.sleep(15)
        print("\nStopping Bybit client...")
        await bybit_client.stop()
        await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Stopping Bybit client...")
        await bybit_client.stop()

    print("Main program finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
