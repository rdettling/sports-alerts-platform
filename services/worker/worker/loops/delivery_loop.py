from __future__ import annotations

import logging
import threading

from worker.config import settings
from worker.db import SessionLocal
from worker.delivery import process_pending_alerts

logger = logging.getLogger(__name__)


def run(stop_event: threading.Event) -> None:
    logger.info("Delivery loop started tick_seconds=%s", settings.delivery_tick_seconds)
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            sent_count, failed_count = process_pending_alerts(db, ingest_run_id=None)
            db.commit()
            if sent_count or failed_count:
                logger.info("Delivery tick sent=%s failed=%s", sent_count, failed_count)
        except Exception:
            db.rollback()
            logger.exception("Delivery tick failed")
        finally:
            db.close()

        stop_event.wait(max(1, settings.delivery_tick_seconds))

    logger.info("Delivery loop stopped")
