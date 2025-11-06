import json
import time

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange, IExchangeClientListener
from exchange_observer.config import GATEIO_WEB_SPOT_PUBLIC, GATEIO_REST_SPOT_INFO, MAX_ARGS_PER_MESSAGE


class GateioClient(BaseExchangeClient):
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__(listener)

    @property
    def exchange(self) -> Exchange:
        return Exchange.GATEIO

    @property
    def websocket_url(self) -> str:
        return GATEIO_WEB_SPOT_PUBLIC

    @property
    def rest_api_url(self) -> str:
        return GATEIO_REST_SPOT_INFO

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

    def parse_symbols(self, data: dict | list[dict]) -> list[str]:
        if not isinstance(data, list):
            self.logger.warning("Symbols data is not a list or API response format changed")
            self.notify_listener("on_error", self.exchange, "Symbols data is not a list or API response format changed")
            return []
        return [s.get("id") for s in data if s.get("trade_status") == "tradable" and s.get("id")]

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
            self.notify_listener("on_error", self.exchange, f"Error sending bulk subscription: {e}")

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
                    self.notify_listener("on_error", self.exchange, f"Subscribe error: {message_data.get('error', '')}")
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
            self.notify_listener("on_error", self.exchange, f"JSON decode error processing message: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing message: {e}")
            self.notify_listener("on_error", self.exchange, f"Unexpected error processing message: {e}")
