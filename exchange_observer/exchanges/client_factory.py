from .binance_client import BinanceClient
from .bybit_client import BybitClient
from .gateio_client import GateioClient
from exchange_observer.core.interfaces import IExchangeClient, IExchangeClientListener
from exchange_observer.core import Exchange


class ExchangeClientFactory:
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        self.listener = listener
        self.clients_map = {
            Exchange.BINANCE: BinanceClient,
            Exchange.BYBIT: BybitClient,
            Exchange.GATEIO: GateioClient,
        }

    def create_client(self, exchange: Exchange) -> IExchangeClient | None:
        client_class = self.clients_map.get(exchange)
        if client_class:
            return client_class(self.listener)
        else:
            return None
