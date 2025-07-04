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
    bid_price: float | None = None
    bid_quantity: float | None = None
    ask_price: float | None = None
    ask_quantity: float | None = None

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

    def to_dict(self) -> dict[str, str | None]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "bid_price": self.bid_price,
            "bid_quantity": self.bid_quantity,
            "ask_price": self.ask_price,
            "ask_quantity": self.ask_quantity,
        }
