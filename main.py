import asyncio
import logging
import signal
from typing import Any

from exchange_observer.app import ExchangeObserverApp
from exchange_observer.core.models import Exchange
from exchange_observer.utils import setup_logging


def arbitrage_opportunity_callback(opportunity: dict[str, Any]):
    logging.info(f"GUI_UPDATE: Arbitrage opportunity found: {opportunity}")


async def main():
    setup_logging(level=logging.INFO)
    logger = logging.getLogger("main")

    EXCHANGES_TO_MONITOR = [Exchange.BINANCE, Exchange.BYBIT, Exchange.GATEIO]
    MIN_ARBITRAGE_PROFIT_PERCENT = 0.1

    app = ExchangeObserverApp(
        exchanges_to_monitor=EXCHANGES_TO_MONITOR,
        min_arbitrage_profit_percent=MIN_ARBITRAGE_PROFIT_PERCENT,
        arbitrage_callback=arbitrage_opportunity_callback,
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_shutdown(sig, frame):
        logger.info(f"Received shutdown signal {sig}. Triggering graceful shutdown...")
        if not stop_event.is_set():
            loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        await app.start()
        await stop_event.wait()
    finally:
        await app.stop()
        logger.info("Application stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("main").info("Application terminated by user.")
