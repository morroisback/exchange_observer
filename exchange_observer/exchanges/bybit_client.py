import aiohttp
import json

from typing import Callable

from .base_client import BaseExchangeClient
from exchange_observer.core import PriceData, Exchange

from exchange_observer.config import BYBIT_WEB_SPOT_PUBLIC, BYBIT_REST_SPOT_INFO, BYBIT_MAX_ARGS_PER_MESSAGE


class BybitClient(BaseExchangeClient):
    def __init__(
        self,
        on_data_callback: Callable[[dict[str, PriceData]], None] | None = None,
        on_error_callback: Callable[[str], None] | None = None,
        on_connected_callback: Callable[[], None] | None = None,
        on_disconnected_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(on_data_callback, on_error_callback, on_connected_callback, on_disconnected_callback)
        self.websocket_url = BYBIT_WEB_SPOT_PUBLIC
        self.exchange = Exchange.BYBIT

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
                        self.call_error_callback("No symbols found or API response format changed")
                        return []

                    active_symbols = []
                    for s in symbols_list:
                        symbol = s.get("symbol")
                        if s.get("status") == "Trading" and symbol:
                            active_symbols.append(symbol)
                            self.data[symbol] = PriceData(
                                exchange=self.exchange,
                                symbol=symbol,
                                base_coin=s.get("baseCoin"),
                                quote_coin=s.get("quoteCoin"),
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

        subscribe_args = []
        for symbol in symbols:
            subscribe_args.append(f"tickers.{symbol}")
            subscribe_args.append(f"orderbook.1.{symbol}")

        for i in range(0, len(subscribe_args), BYBIT_MAX_ARGS_PER_MESSAGE):
            chunk = subscribe_args[i : i + BYBIT_MAX_ARGS_PER_MESSAGE]
            chunk_num = i // BYBIT_MAX_ARGS_PER_MESSAGE + 1
            subscribe_message = json.dumps({"op": "subscribe", "args": chunk})

            try:
                await self.websocket.send(subscribe_message)
                self.logger.info(f"Sent subscribe for {len(chunk) // 2} symbols in chunk {chunk_num}")
                # await asyncio.sleep(0.05)
            except Exception as e:
                self.logger.error(f"Error sending subscription chunk {chunk_num}: {e}")
                self.call_error_callback(f"Error sending subscription chunk {chunk_num}: {e}")
                break

    def process_message(self, message: str) -> None:
        try:
            message_data = json.loads(message)

            if message_data.get("op") == "subscribe":
                if not message_data.get("success", False):
                    self.logger.warning(f"Subscribe error: {message_data.get('ret_msg', '')}")
                    self.call_error_callback(f"Subscribe error: {message_data.get('ret_msg', '')}")
                return

            if "topic" in message_data and "data" in message_data:
                item_data = message_data["data"]

                symbol = ""
                symbol_price_data = {}

                if "tickers" in message_data["topic"]:
                    symbol = item_data.get("symbol")
                    symbol_price_data = {"last_price": item_data.get("lastPrice")}
                elif "orderbook" in message_data["topic"]:
                    symbol = item_data.get("s")
                    bids = item_data["b"]
                    asks = item_data["a"]

                    if bids and len(bids) > 0:
                        symbol_price_data["bid_price"] = bids[0][0]
                        symbol_price_data["bid_quantity"] = bids[0][1]
                    if asks and len(asks) > 0:
                        symbol_price_data["ask_price"] = asks[0][0]
                        symbol_price_data["ask_quantity"] = asks[0][1]

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
