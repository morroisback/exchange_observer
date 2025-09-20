import asyncio
import threading

from exchange_observer.core.interfaces import IAsyncTask


class AsyncWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start_task(self, task: IAsyncTask):
        if self.loop:
            return asyncio.run_coroutine_threadsafe(task.start(), self.loop)
        return None

    def stop_task(self, task: IAsyncTask):
        if self.loop:
            return asyncio.run_coroutine_threadsafe(task.stop(), self.loop)
        return None

    def stop_loop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
