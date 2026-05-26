import logging
import signal
import threading

from worker.config import settings
from worker import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")
SCHEDULER_MAX_SLEEP_SECONDS = 300

_stop_event = threading.Event()


def _stop_worker(*_: object) -> None:
    _stop_event.set()
    logger.info("Shutdown signal received")


def main() -> None:
    signal.signal(signal.SIGINT, _stop_worker)
    signal.signal(signal.SIGTERM, _stop_worker)

    logger.info(
        "Worker started provider=%s scheduler_max_sleep=%ss intervals(catalog=%ss nba_live=%ss mlb_live=%ss)",
        settings.nba_provider,
        SCHEDULER_MAX_SLEEP_SECONDS,
        settings.catalog_sync_interval_seconds,
        settings.nba_live_sync_interval_seconds,
        settings.mlb_live_sync_interval_seconds,
    )
    scheduler.run(_stop_event)
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
