import aiohttp
import json
import time

from typing import Callable

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange

from exchange_observer.config import GATEIO_WEB_SPOT_PUBLIC, GATEIO_REST_SPOT_INFO


class GateioClient(BaseExchangeClient):
    def __init__(
        self,
        on_data_callback: Callable[[dict[str, PriceData]], None] | None = None,
        on_error_callback: Callable[[str], None] | None = None,
        on_connected_callback: Callable[[], None] | None = None,
        on_disconnected_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(on_data_callback, on_error_callback, on_connected_callback, on_disconnected_callback)
        self.websocket_url = GATEIO_WEB_SPOT_PUBLIC
        self.exchange = Exchange.GATEIO

    async def fetch_symbols(self) -> list[str]:
        self.logger.info("Fetching symbols from REST API...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GATEIO_REST_SPOT_INFO) as response:
                    response.raise_for_status()
                    symbols_list = await response.json()

                    if not symbols_list:
                        self.logger.warning("No symbols found or API response format changed")
                        self.call_error_callback("No symbols found or API response format changed")
                        return []

                    active_symbols = []
                    for s in symbols_list:
                        symbol = s.get("id")
                        if s.get("trade_status") == "tradable" and symbol:
                            active_symbols.append(symbol)
                            symbol = symbol.replace("_", "")
                            self.data[symbol] = PriceData(
                                exchange=self.exchange,
                                symbol=symbol,
                                base_coin=s.get("base"),
                                quote_coin=s.get("quote"),
                            )

                    self.logger.info(f"Found {len(active_symbols)} active symbols with coin info")
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

    async def subscribe_symbols(self, symbols: list[str]) -> None:
        if not self.websocket:
            self.logger.error("WebSocket not connected for subscription")
            return

        tickers_subscribe_message = json.dumps(
            {
                "time": int(time.time()),
                "channel": "spot.tickers",
                "event": "subscribe",
                "payload": symbols,
            }
        )

        book_ticker_subscribe_message = json.dumps(
            {
                "time": int(time.time()),
                "channel": "spot.book_ticker",
                "event": "subscribe",
                "payload": symbols,
            }
        )

        try:
            await self.websocket.send(tickers_subscribe_message)
            await self.websocket.send(book_ticker_subscribe_message)
            self.logger.info(f"Sent subscribe for {len(symbols)} symbols")
            # await asyncio.sleep(0.05)
        except Exception as e:
            self.logger.error(f"Error sending bulk subscription: {e}")
            self.call_error_callback(f"Error sending bulk subscription: {e}")

    def process_message(self, message: str) -> None:
        try:
            message_data = json.loads(message)
            event_type = message_data.get("event")
            item_data = message_data.get("result", {})

            if event_type == "subscribe":
                if item_data.get("status") != "success":
                    self.logger.warning(f"Subscribe error: {message_data.get('error', '')}")
                    self.call_error_callback(f"Subscribe error: {message_data.get('error', '')}")
                return

            if event_type == "update" and "channel" in message_data:
                symbol = ""
                symbol_price_data = {}

                if "tickers" in message_data["channel"]:
                    symbol = item_data.get("currency_pair", "").replace("_", "")
                    symbol_price_data = {"last_price": item_data.get("last")}
                elif "book_ticker" in message_data["channel"]:
                    symbol = item_data.get("s", "").replace("_", "")
                    symbol_price_data = {
                        "bid_price": item_data.get("b"),
                        "bid_quantity": item_data.get("B"),
                        "ask_price": item_data.get("a"),
                        "ask_quantity": item_data.get("A"),
                    }

                if symbol and symbol_price_data:
                    if symbol not in self.data:
                        self.logger.warning(f"Skipping update for {symbol}: not initialized with full coin info")
                        return
                    self.data[symbol].update(symbol_price_data)
                    self.call_data_callback({symbol: self.data[symbol]})
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error processing message: {e}")
            self.call_error_callback(f"JSON decode error processing message: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing message: {e}")
            self.call_error_callback(f"Unexpected error processing message: {e}")
