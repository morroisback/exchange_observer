from dataclasses import dataclass
from enum import StrEnum


class Exchange(StrEnum):
    NONE = ""
    BINANCE = "Binance"
    BYBIT = "Bybit"
    GATEIO = "Gate.io"


@dataclass
class PriceData:
    exchange: Exchange
    symbol: str
    base_coin: str | None = None
    quote_coin: str | None = None
    last_price: str | None = None
    bid_price: str | None = None
    bid_quantity: str | None = None
    ask_price: str | None = None
    ask_quantity: str | None = None

    def update(self, data: dict[str, str]) -> None:
        if "last_price" in data:
            self.last_price = data["last_price"]
        if "bid_price" in data:
            self.bid_price = data["bid_price"]
        if "bid_quantity" in data:
            self.bid_quantity = data["bid_quantity"]
        if "ask_price" in data:
            self.ask_price = data["ask_price"]
        if "ask_quantity" in data:
            self.ask_quantity = data["ask_quantity"]

    def to_dict(self) -> dict[str, str | None]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "base_coin": self.base_coin,
            "quote_coin": self.quote_coin,
            "last_price": self.last_price,
            "bid_price": self.bid_price,
            "bid_quantity": self.bid_quantity,
            "ask_price": self.ask_price,
            "ask_quantity": self.ask_quantity,
        }
