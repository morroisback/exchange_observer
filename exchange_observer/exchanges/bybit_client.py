import aiohttp
import json

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange, IExchangeClientListener
from exchange_observer.config import BYBIT_WEB_SPOT_PUBLIC, BYBIT_REST_SPOT_INFO, MAX_ARGS_PER_MESSAGE


class BybitClient(BaseExchangeClient):
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__(listener)
        self.websocket_url = BYBIT_WEB_SPOT_PUBLIC
        self.exchange = Exchange.BYBIT

    def is_ping_message(self, message: str) -> bool:
        return isinstance(message, str) and '"op":"ping"' in message

    def is_pong_message(self, message: str) -> bool:
        return isinstance(message, str) and '"op":"pong"' in message

    async def fetch_symbols(self) -> list[str]:
        self.logger.info("Fetching symbols from REST API...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BYBIT_REST_SPOT_INFO) as response:
                    response.raise_for_status()
                    data = await response.json()

                    symbols_list = data.get("result", {}).get("list", [])
                    if not symbols_list:
                        self.logger.warning("No symbols found or API response format changed")
                        self.notify_listener("on_error", "No symbols found or API response format changed")
                        return []

                    active_symbols = []
                    for s in symbols_list:
                        symbol = s.get("symbol")
                        if s.get("status") == "Trading" and symbol:
                            active_symbols.append(symbol)

                    self.logger.info(f"Found {len(active_symbols)} active symbols with coin info")
                    return active_symbols

        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching symbols: {e}")
            self.notify_listener("on_error", f"HTTP error fetching symbols: {e}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error fetching symbols: {e}")
            self.notify_listener("on_error", f"JSON decode error fetching symbols: {e}")
            return []
        except Exception as e:
            self.logger.exception(f"Unexpected error fetching symbols: {e}")
            self.notify_listener("on_error", f"Unexpected error fetching symbols: {e}")
            return []

    async def subscribe_symbols(self, symbols: list[str]) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for subscription")
            return

        subscribe_args = []
        for symbol in symbols:
            subscribe_args.append(f"orderbook.1.{symbol}")

        try:
            for i in range(0, len(subscribe_args), MAX_ARGS_PER_MESSAGE):
                chunk = subscribe_args[i : i + MAX_ARGS_PER_MESSAGE]
                subscribe_message = json.dumps({"op": "subscribe", "args": chunk})

                await self.websocket.send(subscribe_message)

            self.logger.info(f"Sent subscribe for {len(symbols)} symbol")

        except Exception as e:
            self.logger.error(f"Error sending bulk subscription: {e}")
            self.notify_listener("on_error", f"Error sending bulk subscription: {e}")

    async def send_ping(self) -> None:
        if self.websocket:
            self.logger.info("Sending ping to server")
            ping_message = json.dumps({"op": "ping"})
            await self.websocket.send(ping_message)

    async def handle_ping(self, message: str) -> None:
        self.logger.info("Received ping from server, sending pong")
        if self.websocket:
            pong_message = json.dumps({"op": "pong"})
            await self.websocket.send(pong_message)

    async def handle_pong(self, message: str) -> None:
        self.logger.info("Received pong from server")

    async def handle_message(self, message: str) -> None:
        try:
            message_data: dict = json.loads(message)

            if message_data.get("op") == "subscribe":
                if not message_data.get("success", False):
                    self.logger.warning(f"Subscribe error: {message_data.get('ret_msg', '')}")
                    self.notify_listener("on_error", f"Subscribe error: {message_data.get('ret_msg', '')}")
                return

            if "topic" in message_data and "orderbook" in message_data["topic"] and "data" in message_data:
                item_data: dict = message_data["data"]
                symbol = item_data.get("s", "")
                bids = item_data.get("b", "")
                asks = item_data.get("a", "")

                if symbol and bids and asks:
                    price_data = PriceData(
                        exchange=self.exchange,
                        symbol=symbol,
                        bid_price=float(bids[0][0]),
                        bid_quantity=float(bids[0][1]),
                        ask_price=float(asks[0][0]),
                        ask_quantity=float(asks[0][1]),
                    )
                    self.notify_listener("on_data_received", price_data)

        except (ValueError, TypeError):
            pass
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error processing message: {e}")
            self.notify_listener("on_error", f"JSON decode error processing message: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing message: {e}")
            self.notify_listener("on_error", f"Unexpected error processing message: {e}")
