import logging
import signal
import sys
import threading

from typing import Callable

from PyQt6.QtWidgets import QApplication

from exchange_observer.core import Exchange, ArbitrageOpportunity
from exchange_observer.utils import AsyncWorker, setup_logging

from exchange_observer import ExchangeObserverApp
from exchange_observer import MainWindow


def arbitrage_opportunity_callback(opportunities: list[ArbitrageOpportunity]) -> None:
    for opportunity in opportunities:
        logging.info(f"CALLBACK: Arbitrage opportunity found: {opportunity}")


def main_console(arbitrage_callback: Callable[[list[ArbitrageOpportunity]], None]) -> None:
    logger = logging.getLogger("main_console")

    worker = AsyncWorker()
    worker.start()

    EXCHANGES_TO_MONITOR = [Exchange.BINANCE, Exchange.BYBIT, Exchange.GATEIO]
    ARBITRAGE_CHECK_INTERVAL_SECONDS = 10
    MIN_ARBITRAGE_PROFIT_PERCENT = 0.01
    MAX_DATA_AGE_SECONDS = 60

    app = ExchangeObserverApp(
        exchanges_to_monitor=EXCHANGES_TO_MONITOR,
        arbitrage_check_interval_seconds=ARBITRAGE_CHECK_INTERVAL_SECONDS,
        min_arbitrage_profit_percent=MIN_ARBITRAGE_PROFIT_PERCENT,
        max_data_age_seconds=MAX_DATA_AGE_SECONDS,
        arbitrage_callback=arbitrage_callback,
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
    logger.info("Application stopped")


def main_gui() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def main() -> None:
    setup_logging(level=logging.INFO)
    # main_console(arbitrage_opportunity_callback)
    main_gui()


if __name__ == "__main__":
    main()
