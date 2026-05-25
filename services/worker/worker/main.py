import logging
import signal
import threading

from worker.config import settings
from worker import scheduler

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
        "Worker started provider=%s scheduler_max_sleep=%ss intervals(catalog=%ss live=%ss)",
        settings.nba_provider,
        settings.scheduler_max_sleep_seconds,
        settings.catalog_sync_interval_seconds,
        settings.live_sync_interval_seconds,
    )
    scheduler.run(_stop_event)
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
