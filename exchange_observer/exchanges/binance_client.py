import aiohttp
import json

from typing import Any

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange, IExchangeClientListener
from exchange_observer.config import BINANCE_WEB_SPOT_PUBLIC, BINANCE_REST_SPOT_INFO


class BinanceClient(BaseExchangeClient):
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__(listener)
        self.websocket_url = BINANCE_WEB_SPOT_PUBLIC
        self.exchange = Exchange.BINANCE

    def is_ping_message(self, message: str) -> bool:
        return False

    def is_pong_message(self, message: str) -> bool:
        return False

    async def fetch_symbols(self) -> list[str]:
        self.logger.info("Fetching symbols from REST API...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BINANCE_REST_SPOT_INFO) as response:
                    response.raise_for_status()
                    data = await response.json()

                    symbols_list = data.get("symbols", [])
                    if not symbols_list:
                        self.logger.warning("No symbols found or API response format changed")
                        self.notify_listener("on_error", "No symbols found or API response format changed")
                        return []

                    active_symbols = []
                    for s in symbols_list:
                        symbol = s.get("symbol")
                        if s.get("status") == "TRADING" and symbol:
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

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error processing message: {e}")
            self.notify_listener("on_error", f"JSON decode error processing message: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing message: {e}")
            self.notify_listener("on_error", f"Unexpected error processing message: {e}")

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
