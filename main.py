import logging
import signal
import threading
from typing import Any

from exchange_observer.app import ExchangeObserverApp
from exchange_observer.core import Exchange
from exchange_observer.utils import AsyncWorker, setup_logging

def arbitrage_opportunity_callback(opportunity: dict[str, Any]):
    logging.info(f"CALLBACK: Arbitrage opportunity found: {opportunity}")


def main():
    setup_logging(level=logging.INFO)
    logger = logging.getLogger("main")

    worker = AsyncWorker()
    worker.start()

    EXCHANGES_TO_MONITOR = [Exchange.BINANCE, Exchange.BYBIT, Exchange.GATEIO]
    ARBITRAGE_CHECK_INTERVAL_SECONDS = 5
    MIN_ARBITRAGE_PROFIT_PERCENT = 0.01
    MAX_DATA_AGE_SECONDS = 10

    app = ExchangeObserverApp(
        exchanges_to_monitor=EXCHANGES_TO_MONITOR,
        arbitrage_check_interval_seconds=ARBITRAGE_CHECK_INTERVAL_SECONDS,
        min_arbitrage_profit_percent=MIN_ARBITRAGE_PROFIT_PERCENT,
        max_data_age_seconds=MAX_DATA_AGE_SECONDS,
        arbitrage_callback=arbitrage_opportunity_callback,
    )

    logger.info("Starting application via AsyncWorker...")
    worker.start_task(app)

    stop_event = threading.Event()

    def handle_shutdown(sig, frame):
        logger.info(f"Received shutdown signal {sig}. Triggering graceful shutdown...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    stop_event.wait()

    logger.info("Stopping application...")
    future = worker.stop_task(app)
    if future:
        try:
            future.result()
        except Exception as e:
            logger.error(f"Error while stopping application: {e}")
    
    worker.stop_loop()
    worker.join()
    logger.info("Application stopped.")

if __name__ == "__main__":
    main()
