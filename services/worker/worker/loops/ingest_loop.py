from __future__ import annotations

import logging
import threading

from worker.config import settings
from worker.ingest import run_ingest_cycle
from worker.providers.factory import get_provider

logger = logging.getLogger(__name__)


def run(stop_event: threading.Event) -> None:
    provider = get_provider()
    logger.info("Ingest loop started provider=%s", settings.nba_provider)

    while not stop_event.is_set():
        result = run_ingest_cycle(provider=provider)
        next_poll_seconds = int(result.get("next_poll_seconds", settings.ingest_interval_active_seconds))
        logger.info("Ingest cycle complete result=%s next_poll_seconds=%s", result, next_poll_seconds)
        stop_event.wait(max(1, next_poll_seconds))

    logger.info("Ingest loop stopped")
