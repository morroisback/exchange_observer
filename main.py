import asyncio

from exchange_observer.core import ExchangeDataManager, Exchange
from exchange_observer.core import PriceData
from exchange_observer.exchanges import BinanceClient, BybitClient, GateioClient

from exchange_observer.utils import setup_logging


async def test_clients() -> None:
    exchange = Exchange.BINANCE

    def handle_data(data: PriceData) -> None:
        print(f"{exchange} received data for {data.symbol}: Last Price={data.last_price}")

    def handle_error(msg: str) -> None:
        print(f"{exchange} error: {msg}")

    def handle_connected() -> None:
        print(f"{exchange} client connected!")

    def handle_disconnected() -> None:
        print(f"{exchange} client disconnected!")

    client = BinanceClient(
        on_data_callback=handle_data,
        on_error_callback=handle_error,
        on_connected_callback=handle_connected,
        on_disconnected_callback=handle_disconnected,
    )

    await client.start()
    print(f"{exchange} client started. Waiting for data...")

    try:
        await asyncio.sleep(60)
        print(f"\nStopping {exchange} client...")
        await client.stop()
        await asyncio.sleep(2)
    except KeyboardInterrupt:
        print(f"\nKeyboardInterrupt detected. Stopping {exchange} client...")
        await client.stop()

    print("Test client program finished")


async def test_manager() -> None:
    manager = ExchangeDataManager(
        exchange_to_monitor=[Exchange.BINANCE, Exchange.BYBIT, Exchange.GATEIO],
        arbitrage_check_interval_seconds=5,
        min_arbitrage_profit_percent=0.01,
        max_data_age_seconds=10
    )

    await manager.start()
    print("Manager started. Waiting for data...")

    try:
        await asyncio.sleep(60)
        print("\nStopping manager...")
        await manager.stop()
        await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Stopping manager...")
    
    print("Test manager program finished")


async def main() -> None:
    setup_logging()

    # await test_clients()
    await test_manager()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
