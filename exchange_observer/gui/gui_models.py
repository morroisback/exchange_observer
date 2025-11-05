from dataclasses import dataclass
from enum import StrEnum


class FilterMode(StrEnum):
    ALL = "ALL"
    WHITELIST = "WHITELIST"
    ONLY_BTC = "ONLY_BTC"
    ONLY_ETH = "ONLY_ETH"
    ONLY_USDT = "ONLY_USDT"


@dataclass
class FilterSettings:
    mode: FilterMode
    whitelist: list[str]
    blacklist: list[str]


@dataclass
class AppSettings:
    exchanges: dict[str, bool]
    arbitrage_check_interval_seconds: int
    min_arbitrage_profit_percent: float
    max_data_age_seconds: int
