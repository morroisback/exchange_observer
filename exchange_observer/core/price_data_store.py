import pandas as pd

from datetime import datetime, timedelta, timezone
from itertools import permutations

from .models import ArbitrageOpportunity, PriceData, Exchange


class PriceDataStore:
    COLUMNS = [
        "exchange",
        "symbol",
        "bid_price",
        "bid_quantity",
        "ask_price",
        "ask_quantity",
        "timestamp_utc",
    ]

    DTYPE_MAP = {
        "exchange": str,
        "symbol": str,
        "bid_price": float,
        "bid_quantity": float,
        "ask_price": float,
        "ask_quantity": float,
        "timestamp_utc": "datetime64[ns, UTC]",
    }

    def __init__(self) -> None:
        self.df = pd.DataFrame(columns=self.COLUMNS).astype(self.DTYPE_MAP)
        self.df.set_index(["exchange", "symbol"], inplace=True)

    def update_price_data(self, price_data: PriceData) -> None:
        current_utc_time = datetime.now(timezone.utc)

        idx = (price_data.exchange.value, price_data.symbol)
        data_to_update = {
            "bid_price": price_data.bid_price,
            "bid_quantity": price_data.bid_quantity,
            "ask_price": price_data.ask_price,
            "ask_quantity": price_data.ask_quantity,
            "timestamp_utc": current_utc_time,
        }

        for col_name, value in data_to_update.items():
            self.df.loc[idx, col_name] = value

    def get_dataframe(self) -> pd.DataFrame:
        return self.df.copy()

    def get_data_for_symbol(self, exchange: Exchange, symbol: str) -> PriceData | None:
        try:
            row = self.df.loc[(exchange.value, symbol)]
            return PriceData(
                exchange=exchange,
                symbol=symbol,
                bid_price=row["bid_price"],
                bid_quantity=row["bid_quantity"],
                ask_price=row["ask_price"],
                ask_quantity=row["ask_quantity"],
            )
        except KeyError:
            return None

    def find_arbitrage_opportunities(
        self, min_profit_percent: float = 0.1, max_data_age_seconds: int = 10
    ) -> list[ArbitrageOpportunity]:
        opportunities: list[ArbitrageOpportunity] = []
        current_utc_time = datetime.now(timezone.utc)

        df_temp = self.df.reset_index()
        fresh_data_df = df_temp[
            (current_utc_time - df_temp["timestamp_utc"] <= timedelta(seconds=max_data_age_seconds))
        ]

        for symbol_name, group in fresh_data_df.groupby("symbol"):
            if len(group) < 2:
                continue

            valid_prices_group = group.dropna(subset=["bid_price", "ask_price"])
            if len(valid_prices_group) < 2:
                continue

            for (_, buy_row), (_, sell_row) in permutations(valid_prices_group.iterrows(), 2):
                buy_price = buy_row["ask_price"]
                sell_price = sell_row["bid_price"]

                profit_percent = (sell_price - buy_price) / buy_price

                MAX_ACCEPTABLE_PROFIT_PERCENT = 0.5
                if profit_percent >= min_profit_percent and profit_percent < MAX_ACCEPTABLE_PROFIT_PERCENT:
                    last_updated_buy: datetime = buy_row["timestamp_utc"]
                    last_updated_sell: datetime = sell_row["timestamp_utc"]

                    opportunity = ArbitrageOpportunity(
                        symbol=symbol_name,
                        buy_exchange=buy_row["exchange"],
                        buy_price=buy_price,
                        buy_bid=buy_row["bid_price"],
                        buy_ask=buy_row["ask_price"],
                        sell_exchange=sell_row["exchange"],
                        sell_price=sell_price,
                        sell_bid=sell_row["bid_price"],
                        sell_ask=sell_row["ask_price"],
                        profit_percent=profit_percent * 100,
                        last_updated_buy=last_updated_buy,
                        last_updated_sell=last_updated_sell,
                        buy_data_age=(current_utc_time - last_updated_buy).total_seconds(),
                        sell_data_age=(current_utc_time - last_updated_sell).total_seconds(),
                    )
                    opportunities.append(opportunity)

        return opportunities
