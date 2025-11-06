from .binance_client import BinanceClient
from .bybit_client import BybitClient
from .gateio_client import GateioClient
from exchange_observer.core import Exchange, IAsyncTask, IExchangeClientListener


class ExchangeClientFactory:
    def __init__(self, listener: IExchangeClientListener | None = None) -> None:
        self.listener = listener
        self.clients_map = {
            Exchange.BINANCE: BinanceClient,
            Exchange.BYBIT: BybitClient,
            Exchange.GATEIO: GateioClient,
        }

    def create_client(self, exchange: Exchange) -> IAsyncTask | None:
        client_class = self.clients_map.get(exchange)
        if client_class:
            return client_class(self.listener)
        else:
            return None
