import aiohttp
import json
import time

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange, IExchangeClientListener
from exchange_observer.config import GATEIO_WEB_SPOT_PUBLIC, GATEIO_REST_SPOT_INFO, MAX_ARGS_PER_MESSAGE


class GateioClient(BaseExchangeClient):
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__(listener)
        self.websocket_url = GATEIO_WEB_SPOT_PUBLIC
        self.exchange = Exchange.GATEIO

    def is_ping_message(self, message: str) -> bool:
        try:
            data: dict = json.loads(message)
            return data.get("channel") == "spot.ping"
        except json.JSONDecodeError:
            return False

    def is_pong_message(self, message: str) -> bool:
        try:
            data: dict = json.loads(message)
            return data.get("channel") == "spot.pong"
        except json.JSONDecodeError:
            return False

    async def fetch_symbols(self) -> list[str]:
        self.logger.info("Fetching symbols from REST API...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GATEIO_REST_SPOT_INFO) as response:
                    response.raise_for_status()
                    symbols_list = await response.json()

                    if not symbols_list:
                        self.logger.warning("No symbols found or API response format changed")
                        self.notify_listener("on_error", "No symbols found or API response format changed")
                        return []

                    active_symbols = []
                    for s in symbols_list:
                        symbol = s.get("id")
                        if s.get("trade_status") == "tradable" and symbol:
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

        try:
            for i in range(0, len(symbols), MAX_ARGS_PER_MESSAGE):
                chunk = symbols[i : i + MAX_ARGS_PER_MESSAGE]
                subscribe_message = json.dumps(
                    {"time": int(time.time()), "channel": "spot.book_ticker", "event": "subscribe", "payload": chunk}
                )

                await self.websocket.send(subscribe_message)
            self.logger.info(f"Sent subscribe for {len(symbols)} symbols")

        except Exception as e:
            self.logger.error(f"Error sending bulk subscription: {e}")
            self.notify_listener("on_error", f"Error sending bulk subscription: {e}")

    async def send_ping(self) -> None:
        if self.websocket:
            self.logger.info("Sending ping to server")
            ping_message = json.dumps({"time": int(time.time()), "channel": "spot.ping"})
            await self.websocket.send(ping_message)

    async def handle_ping(self, message: str) -> None:
        self.logger.info("Received ping from server, sending pong")
        if self.websocket:
            pong_message = json.dumps({"time": int(time.time()), "channel": "spot.pong"})
            await self.websocket.send(pong_message)

    async def handle_pong(self, message: str) -> None:
        self.logger.info("Received pong from server")

    async def handle_message(self, message: str) -> None:
        try:
            message_data: dict = json.loads(message)
            event_type = message_data.get("event")
            item_data: dict = message_data.get("result", {})

            if event_type == "subscribe":
                if item_data.get("status") != "success":
                    self.logger.warning(f"Subscribe error: {message_data.get('error', '')}")
                    self.notify_listener("on_error", f"Subscribe error: {message_data.get('error', '')}")
                return

            if event_type == "update" and "channel" in message_data and "book_ticker" in message_data["channel"]:
                symbol = item_data.get("s", "").replace("_", "")

                if symbol:
                    price_data = PriceData(
                        exchange=self.exchange,
                        symbol=symbol,
                        bid_price=float(item_data.get("b")),
                        bid_quantity=float(item_data.get("B")),
                        ask_price=float(item_data.get("a")),
                        ask_quantity=float(item_data.get("A")),
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
