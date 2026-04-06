import logging
import signal
import time

from worker.config import settings
from worker.ingest import run_ingest_cycle
from worker.providers.factory import get_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")

_keep_running = True


def _stop_worker(*_: object) -> None:
    global _keep_running
    _keep_running = False
    logger.info("Shutdown signal received")


def main() -> None:
    signal.signal(signal.SIGINT, _stop_worker)
    signal.signal(signal.SIGTERM, _stop_worker)

    provider = get_provider()
    logger.info(
        "Worker started with provider=%s base_interval=%ss",
        settings.nba_provider,
        settings.worker_poll_interval_seconds,
    )

    while _keep_running:
        result = run_ingest_cycle(provider=provider)
        next_poll_seconds = int(result.get("next_poll_seconds", settings.worker_poll_interval_seconds))
        logger.info("Ingest cycle complete result=%s next_poll_seconds=%s", result, next_poll_seconds)
        for _ in range(next_poll_seconds):
            if not _keep_running:
                break
            time.sleep(1)

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
