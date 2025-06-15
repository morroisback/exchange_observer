from dataclasses import dataclass


@dataclass
class PriceData:
    symbol: str
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
            "symbol": self.symbol,
            "last_price": self.last_price,
            "bid_price": self.bid_price,
            "bid_quantity": self.bid_quantity,
            "ask_price": self.ask_price,
            "ask_quantity": self.ask_quantity,
        }
