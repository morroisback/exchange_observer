from abc import ABC, abstractmethod

from exchange_observer.core.models import PriceData


class IExchangeClient(ABC):
    @abstractmethod
    async def fetch_symbols(self) -> list[str]:
        pass

    @abstractmethod
    async def subscribe_symbols(self) -> None:
        pass

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    def get_data(self, symbol: str | None = None) -> dict[str, PriceData] | PriceData | None:
        pass
