import asyncio
import threading
from contextlib import asynccontextmanager

from app.worker import scheduler, updates
from app.worker.delivery import run_delivery_loop


@asynccontextmanager
async def running_worker():
    stop = threading.Event()
    wake_delivery = threading.Event()
    updates.event_loop = asyncio.get_running_loop()
    threads = (
        threading.Thread(
            target=scheduler.run,
            args=(stop, wake_delivery),
            name="game-sync",
            daemon=True,
        ),
        threading.Thread(
            target=run_delivery_loop,
            args=(stop, wake_delivery),
            name="alert-delivery",
            daemon=True,
        ),
    )
    try:
        for thread in threads:
            thread.start()
        yield threads
    finally:
        stop.set()
        wake_delivery.set()
        for thread in threads:
            if thread.ident is not None:
                await asyncio.to_thread(thread.join)
        updates.event_loop = None
