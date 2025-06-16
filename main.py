import asyncio

from exchange_observer.core.models import PriceData
from exchange_observer.exchanges import BinanceClient, BybitClient
from exchange_observer.utils.logger_config import setup_logging


async def main() -> None:
    setup_logging()

    def handle_data(data: dict[str, PriceData]) -> None:
        for s, pd in data.items():
            print(f"Received data for {s}: Last Price={pd.last_price}, Bid={pd.bid_price}, Ask={pd.ask_price}")

    def handle_error(msg: str) -> None:
        print(f"Error: {msg}")

    def handle_connected() -> None:
        print("Bybit client connected!")

    def handle_disconnected() -> None:
        print("Bybit client disconnected!")

    client = BinanceClient(
        on_data_callback=handle_data,
        on_error_callback=handle_error,
        on_connected_callback=handle_connected,
        on_disconnected_callback=handle_disconnected,
    )

    # client = BybitClient(
    #     on_data_callback=handle_data,
    #     on_error_callback=handle_error,
    #     on_connected_callback=handle_connected,
    #     on_disconnected_callback=handle_disconnected,
    # )
    await client.start()
    print("Bybit client started. Waiting for data...")

    try:
        await asyncio.sleep(15)
        print("\nStopping Bybit client...")
        await client.stop()
        await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Stopping Bybit client...")
        await client.stop()

    print("Main program finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
