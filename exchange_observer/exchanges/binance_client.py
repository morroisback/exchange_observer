import aiohttp
import json

from typing import Any

from .base_client import BaseExchangeClient
from exchange_observer.core.interfaces import IExchangeClientListener
from exchange_observer.core.models import PriceData, Exchange

from exchange_observer.config import BINANCE_WEB_SPOT_PUBLIC, BINANCE_REST_SPOT_INFO


class BinanceClient(BaseExchangeClient):
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        super().__init__(listener)
        self.websocket_url = BINANCE_WEB_SPOT_PUBLIC
        self.exchange = Exchange.BINANCE

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

    async def subscribe_symbols(self, _: list[str]) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for subscription")
            return

    def process_message(self, message: str) -> None:
        try:
            message_data = json.loads(message)
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
            symbol_price_data = {
                "bid_price": item_data.get("b"),
                "bid_quantity": item_data.get("B"),
                "ask_price": item_data.get("a"),
                "ask_quantity": item_data.get("A"),
            }
            price_data = PriceData(exchange=self.exchange, symbol=symbol)
            price_data.update(symbol_price_data)

            self.notify_listener("on_price_data", price_data)
