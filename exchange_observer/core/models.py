from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    bid_price: float | None = None
    bid_quantity: float | None = None
    ask_price: float | None = None
    ask_quantity: float | None = None
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update(self, new_data: dict[str, str]) -> None:
        for key, value in new_data.items():
            if hasattr(self, key) and value is not None:
                if key in ("bid_price", "bid_quantity", "ask_price", "ask_quantity"):
                    try:
                        setattr(self, key, float(value))
                    except (ValueError, TypeError):
                        pass
                else:
                    setattr(self, key, value)

    def to_dict(self) -> dict[str, str | float | None]:
        return {
            "exchange": self.exchange.value,
            "symbol": self.symbol,
            "bid_price": self.bid_price,
            "bid_quantity": self.bid_quantity,
            "ask_price": self.ask_price,
            "ask_quantity": self.ask_quantity,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    buy_price: float
    buy_bid: float
    buy_ask: float
    sell_exchange: str
    sell_price: float
    sell_bid: float
    sell_ask: float
    profit_percent: float
    last_updated_buy: datetime
    last_updated_sell: datetime
    buy_data_age: float | None = None
    sell_data_age: float | None = None

    def to_dict(self) -> dict[str, str | float | datetime | None]:
        return {
            "symbol": self.symbol,
            "buy_exchange": self.buy_exchange,
            "buy_price": self.buy_price,
            "buy_bid": self.buy_bid,
            "buy_ask": self.buy_ask,
            "sell_exchange": self.sell_exchange,
            "sell_price": self.sell_price,
            "sell_bid": self.sell_bid,
            "sell_ask": self.sell_ask,
            "profit_percent": self.profit_percent,
            "last_updated_buy": self.last_updated_buy,
            "last_updated_sell": self.last_updated_sell,
            "buy_data_age": self.buy_data_age,
            "sell_data_age": self.sell_data_age,
        }
