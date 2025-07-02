import pandas as pd

from datetime import datetime, timedelta, timezone

from .models import PriceData, Exchange


class PriceDataStore:
    COLUMNS = [
        "exchange",
        "symbol",
        "base_coin",
        "quote_coin",
        "last_price",
        "bid_price",
        "bid_quantity",
        "ask_price",
        "ask_quantity",
        "timestamp_utc",
    ]

    DTYPE_MAP = {
        "exchange": str,
        "symbol": str,
        "base_coin": str,
        "quote_coin": str,
        "last_price": float,
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
            "base_coin": price_data.base_coin,
            "quote_coin": price_data.quote_coin,
            "last_price": price_data.last_price,
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
                base_coin=row["base_coin"],
                quote_coin=row["quote_coin"],
                last_price=row["last_price"],
                bid_price=row["bid_price"],
                bid_quantity=row["bid_quantity"],
                ask_price=row["ask_price"],
                ask_quantity=row["ask_quantity"],
            )
        except KeyError:
            return None

    def filter_by_coin(self, coin: str) -> pd.DataFrame:
        upper_coin = coin.upper()
        df_reset = self.df.reset_index()
        filtered_df = df_reset[
            (df_reset["base_coin"].str.upper() == upper_coin) | (df_reset["quote_coin"].str.upper() == upper_coin)
        ].set_index(["exchange", "symbol"])
        return filtered_df.copy()

    def filter_by_exchange_and_coin(self, exchange: Exchange, coin: str) -> pd.DataFrame:
        upper_coin = coin.upper()
        df_reset = self.df.reset_index()
        filtered_df = df_reset[
            (df_reset["exchange"] == exchange.value)
            & ((df_reset["base_coin"].str.upper() == upper_coin) | (df_reset["quote_coin"].str.upper() == upper_coin))
        ].set_index(["exchange", "symbol"])
        return filtered_df.copy()

    def find_related_symbols(self, target_exchange: Exchange, reference_symbols: list[str]) -> pd.DataFrame:
        reference_coins = set()
        for symbol in reference_symbols:
            try:
                row = self.df.loc[(target_exchange.value, symbol)]
                if row.get("base_coin"):
                    reference_coins.add(str(row["base_coin"].upper()))
                if row.get("quote_coin"):
                    reference_coins.add(str(row["quote_coin"].upper()))
            except KeyError:
                continue

        if not reference_coins:
            return pd.DataFrame(columns=self.COLUMNS).set_index(["exchange", "symbol"])

        df_reset = self.df.reset_index()
        filtered_df = df_reset[
            (df_reset["exchange"] != target_exchange.value)
            & (
                df_reset["base_coin"].str.upper().isin(reference_coins)
                | df_reset["quote_coin"].str.upper().isin(reference_coins)
            )
        ].set_index(["exchange", "symbol"])
        return filtered_df.copy()

    def find_arbitrage_opportunities(
        self, min_profit_percent: float = 0.1, max_data_age_seconds: int = 10
    ) -> pd.DataFrame:
        opportunities = []
        current_utc_time = datetime.now(timezone.utc)

        df_temp = self.df.reset_index()
        fresh_data_df = df_temp[
            (current_utc_time - df_temp["timestamp_utc"] <= timedelta(seconds=max_data_age_seconds))
        ]

        for symbol_name, group in fresh_data_df.groupby("symbol"):
            if len(group) < 2:
                continue

            valid_prices_group = group.dropna(subset=["bid_price", "ask_price"])
            if valid_prices_group.empty:
                continue

            best_ask_row = valid_prices_group.loc[valid_prices_group["ask_price"].idxmin()]
            best_bid_row = valid_prices_group.loc[valid_prices_group["bid_price"].idxmax()]

            buy_price = best_ask_row["ask_price"]
            sell_price = best_bid_row["bid_price"]

            if best_ask_row["exchange"] == best_bid_row["exchange"]:
                continue

            profit_percent = (sell_price - buy_price) / buy_price

            MAX_ACCEPTABLE_PROFIT_PERCENT = 0.5
            if profit_percent >= min_profit_percent: # and profit_percent < MAX_ACCEPTABLE_PROFIT_PERCENT:
                opportunities.append(
                    {
                        "symbol": symbol_name,
                        "buy_exchange": best_ask_row["exchange"],
                        "buy_price": buy_price,
                        "sell_exchange": best_bid_row["exchange"],
                        "sell_price": sell_price,
                        "profit_percent": profit_percent * 100,
                        "last_updated_buy": best_ask_row["timestamp_utc"],
                        "last_updated_sell": best_bid_row["timestamp_utc"],
                    }
                )

        if opportunities:
            return pd.DataFrame(opportunities).set_index("symbol")
        else:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "buy_exchange",
                    "buy_price",
                    "sell_exchange",
                    "sell_price",
                    "profit_percent",
                    "last_updated_buy",
                    "last_updated_sell",
                ]
            ).set_index("symbol")
