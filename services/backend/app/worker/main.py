import logging
import signal
import threading

from app.db.usage import database_usage_logging
from app.services.competitions import get_competition_profile, list_supported_competitions

from app.worker import scheduler
from app.worker.config import settings
from app.worker.delivery import run_delivery_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("worker")
_stop_event = threading.Event()
_delivery_wake_event = threading.Event()


def _stop_worker(*_: object) -> None:
    _stop_event.set()
    logger.info("Shutdown signal received")


def main() -> None:
    signal.signal(signal.SIGINT, _stop_worker)
    signal.signal(signal.SIGTERM, _stop_worker)

    live_intervals = ", ".join(
        f"{competition.lower()}={get_competition_profile(competition).live_sync_interval_seconds}s"
        for competition in list_supported_competitions()
    )
    logger.info(
        "Worker started intervals(catalog=%ss live=%s)",
        settings.catalog_sync_interval_seconds,
        live_intervals,
    )
    delivery_thread = threading.Thread(
        target=run_delivery_loop,
        args=(_stop_event, _delivery_wake_event),
        name="alert-delivery",
        daemon=True,
    )
    with database_usage_logging():
        delivery_thread.start()
        try:
            scheduler.run(_stop_event, _delivery_wake_event)
        finally:
            _stop_event.set()
            _delivery_wake_event.set()
            delivery_thread.join()
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
