import json

from typing import Any

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange, IExchangeClientListener
from exchange_observer.config import BINANCE_WEB_SPOT_PUBLIC, BINANCE_REST_SPOT_INFO


class BinanceClient(BaseExchangeClient):
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__(listener)

    @property
    def exchange(self) -> Exchange:
        return Exchange.BINANCE

    @property
    def websocket_url(self) -> str:
        return BINANCE_WEB_SPOT_PUBLIC

    @property
    def rest_api_url(self) -> str:
        return BINANCE_REST_SPOT_INFO

    def is_ping_message(self, message: str) -> bool:
        return False

    def is_pong_message(self, message: str) -> bool:
        return False

    def parse_symbols(self, data: dict | list[dict]) -> list[str]:
        symbols_list: list[dict] = data.get("symbols", [])
        if not symbols_list:
            self.logger.warning("No symbols found or API response format changed")
            self.notify_listener("on_error", self.exchange, "No symbols found or API response format changed")
            return []

        return [s.get("symbol") for s in symbols_list if s.get("status") == "TRADING" and s.get("symbol")]

    async def subscribe_symbols(self, symbols: list[str]) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for subscription")
            return

        self.logger.info(f"Sent subscribe for {len(symbols)} symbol")

    async def send_ping(self) -> None:
        if self.websocket:
            self.logger.info("Sending ping to server")
            await self.websocket.ping()

    async def handle_ping(self, message: str) -> None:
        self.logger.info("Received a ping from the server")

    async def handle_pong(self, message: str) -> None:
        self.logger.info("Received a pong from the server")

    async def handle_message(self, message: str) -> None:
        try:
            message_data: dict = json.loads(message)
            if isinstance(message_data, list):
                for item_data in message_data:
                    self.handle_single_item_data(item_data)
            else:
                self.handle_single_item_data(message_data)

        except (ValueError, TypeError):
            pass
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error processing message: {e}")
            self.notify_listener("on_error", self.exchange, f"JSON decode error processing message: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing message: {e}")
            self.notify_listener("on_error", self.exchange, f"Unexpected error processing message: {e}")

    def handle_single_item_data(self, item_data: dict[str, Any]) -> None:
        event_type = item_data.get("e")
        symbol = item_data.get("s")

        if not symbol:
            return

        if event_type == "24hrTicker":
            price_data = PriceData(
                exchange=self.exchange,
                symbol=symbol,
                bid_price=float(item_data.get("b")),
                bid_quantity=float(item_data.get("B")),
                ask_price=float(item_data.get("a")),
                ask_quantity=float(item_data.get("A")),
            )

            self.notify_listener("on_data_received", price_data)
