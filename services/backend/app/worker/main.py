import logging
import signal
import threading

from app.services.leagues import get_league_profile, list_supported_leagues

from app.worker import scheduler
from app.worker.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("worker")
_stop_event = threading.Event()


def _stop_worker(*_: object) -> None:
    _stop_event.set()
    logger.info("Shutdown signal received")


def main() -> None:
    signal.signal(signal.SIGINT, _stop_worker)
    signal.signal(signal.SIGTERM, _stop_worker)

    live_intervals = ", ".join(
        f"{league.lower()}={get_league_profile(league).live_sync_interval_seconds}s"
        for league in list_supported_leagues()
    )
    logger.info(
        "Worker started scheduler_max_sleep=%ss intervals(catalog=%ss live=%s)",
        settings.scheduler_tick_seconds,
        settings.catalog_sync_interval_seconds,
        live_intervals,
    )
    scheduler.run(_stop_event)
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
