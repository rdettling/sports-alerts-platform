from __future__ import annotations

import logging

import httpx

from app.worker.config import settings

logger = logging.getLogger(__name__)
NOTIFICATION_TIMEOUT_SECONDS = 2.0
_delivery_failing = False


def notify_games_changed(competition: str) -> bool:
    global _delivery_failing

    api_url = settings.live_update_api_url.rstrip("/")
    secret = settings.live_update_secret
    if not api_url or not secret:
        return False

    try:
        response = httpx.post(
            f"{api_url}/internal/updates/games",
            headers={"X-Live-Update-Secret": secret},
            json={"competition": competition},
            timeout=NOTIFICATION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as exc:
        if not _delivery_failing:
            logger.warning("Live update delivery failed; later failures will be suppressed: %s", exc)
        _delivery_failing = True
        return False

    if _delivery_failing:
        logger.info("Live update delivery recovered")
    _delivery_failing = False
    return True
