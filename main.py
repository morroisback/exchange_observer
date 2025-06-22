import asyncio

from exchange_observer.core.models import PriceData, Exchange
# from exchange_observer.exchanges import BinanceClient, BybitClient, GateioClient
from exchange_observer.exchanges import BybitClient
from exchange_observer.utils.logger_config import setup_logging


async def main() -> None:
    setup_logging()

    exchange = Exchange.BYBIT

    def handle_data(data: dict[str, PriceData]) -> None:
        for s, pd in data.items():
            print(f"{exchange} received data for {s}: Last Price={pd.last_price}")

    def handle_error(msg: str) -> None:
        print(f"{exchange} error: {msg}")

    def handle_connected() -> None:
        print(f"{exchange} client connected!")

    def handle_disconnected() -> None:
        print(f"{exchange} client disconnected!")

    client = BybitClient(
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

    print("Main program finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
