import logging
import signal
import threading

from worker.config import settings
from worker.loops import delivery_loop, ingest_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")

_stop_event = threading.Event()


def _stop_worker(*_: object) -> None:
    _stop_event.set()
    logger.info("Shutdown signal received")


def main() -> None:
    signal.signal(signal.SIGINT, _stop_worker)
    signal.signal(signal.SIGTERM, _stop_worker)

    logger.info(
        "Worker started provider=%s ingest_live=%ss ingest_active=%ss ingest_idle=%ss delivery_tick=%ss",
        settings.nba_provider,
        settings.ingest_interval_live_seconds,
        settings.ingest_interval_active_seconds,
        settings.ingest_interval_idle_seconds,
        settings.delivery_tick_seconds,
    )
    ingest_thread = threading.Thread(target=ingest_loop.run, args=(_stop_event,), name="ingest-loop", daemon=True)
    delivery_thread = threading.Thread(target=delivery_loop.run, args=(_stop_event,), name="delivery-loop", daemon=True)
    ingest_thread.start()
    delivery_thread.start()
    ingest_thread.join()
    _stop_event.set()
    delivery_thread.join()

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
