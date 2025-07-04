from abc import ABC, abstractmethod


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
