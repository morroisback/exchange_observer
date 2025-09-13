import asyncio
import logging
import signal

from exchange_observer.core import ArbitrageEngine, ExchangeDataManager, PriceDataStore, Exchange
from exchange_observer.exchanges import ExchangeClientFactory
from exchange_observer.utils import setup_logging


async def main():
    """
    Main function to compose and run the application.
    """
    setup_logging(level=logging.INFO)
    logger = logging.getLogger("main")

    EXCHANGES_TO_MONITOR = [Exchange.BINANCE, Exchange.BYBIT, Exchange.GATEIO]
    ARBITRAGE_CHECK_INTERVAL_SECONDS = 5
    MIN_ARBITRAGE_PROFIT_PERCENT = 0.1
    MAX_DATA_AGE_SECONDS = 10

    logger.info("Creating application components...")

    price_data_store = PriceDataStore()
    data_manager = ExchangeDataManager(price_data_store)
    client_factory = ExchangeClientFactory(listener=data_manager)

    clients = {exchange.value: client_factory.create_client(exchange) for exchange in EXCHANGES_TO_MONITOR}
    clients = {name: client for name, client in clients.items() if client is not None}

    arbitrage_engine = ArbitrageEngine(
        price_data_store=price_data_store,
        arbitrage_check_interval_seconds=ARBITRAGE_CHECK_INTERVAL_SECONDS,
        min_arbitrage_profit_percent=MIN_ARBITRAGE_PROFIT_PERCENT,
        max_data_age_seconds=MAX_DATA_AGE_SECONDS,
    )

    logger.info("Wiring up dependencies...")
    data_manager.clients = clients
    data_manager.arbitrage_engine = arbitrage_engine

    logger.info("Starting application...")
    await data_manager.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_shutdown(sig, frame):
        logger.info(f"Received shutdown signal {sig}. Triggering graceful shutdown...")
        if not stop_event.is_set():
            loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    await stop_event.wait()

    logger.info("Stopping application...")
    await data_manager.stop()
    logger.info("Application stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("main").info("Application terminated by user.")
