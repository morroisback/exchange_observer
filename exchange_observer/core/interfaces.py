from abc import ABC, abstractmethod

from .models import PriceData, Exchange


class IAsyncTask(ABC):
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
    def on_error(self, exchange: Exchange, message: str) -> None:
        pass

    @abstractmethod
    def on_connected(self, exchange: Exchange) -> None:
        pass

    @abstractmethod
    def on_disconnected(self, exchange: Exchange) -> None:
        pass
