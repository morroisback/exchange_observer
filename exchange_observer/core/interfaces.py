from abc import ABC, abstractmethod

from .models import PriceData


class IExchangeClient(ABC):
    @abstractmethod
    async def fetch_symbols(self) -> list[str]:
        pass

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass


class IExchangeClientListener(ABC):
    @abstractmethod
    def on_data_received(self, data: PriceData) -> None:
        pass

    @abstractmethod
    def on_error(self, message: str) -> None:
        pass

    @abstractmethod
    def on_connected(self) -> None:
        pass

    @abstractmethod
    def on_disconnected(self) -> None:
        pass
