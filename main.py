import asyncio

from exchange_observer.core.models import PriceData
# from exchange_observer.exchanges import BinanceClient, BybitClient, GateioClient
from exchange_observer.exchanges import GateioClient
from exchange_observer.utils.logger_config import setup_logging


async def main() -> None:
    setup_logging()

    client_name = "Gate.io"

    def handle_data(data: dict[str, PriceData]) -> None:
        for s, pd in data.items():
            print(f"{client_name} received data for {s}: Last Price={pd.last_price}")

    def handle_error(msg: str) -> None:
        print(f"{client_name} error: {msg}")

    def handle_connected() -> None:
        print(f"{client_name} client connected!")

    def handle_disconnected() -> None:
        print(f"{client_name} client disconnected!")

    client = GateioClient(
        on_data_callback=handle_data,
        on_error_callback=handle_error,
        on_connected_callback=handle_connected,
        on_disconnected_callback=handle_disconnected,
    )

    await client.start()
    print(f"{client_name} client started. Waiting for data...")

    try:
        await asyncio.sleep(15)
        print(f"\nStopping {client_name} client...")
        await client.stop()
        await asyncio.sleep(2)
    except KeyboardInterrupt:
        print(f"\nKeyboardInterrupt detected. Stopping {client_name} client...")
        await client.stop()

    print("Main program finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
