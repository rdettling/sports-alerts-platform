from __future__ import annotations

import logging
from time import sleep

import httpx

from app.schemas.schedule import ScheduleSnapshot
from app.worker.config import settings

logger = logging.getLogger(__name__)
NOTIFICATION_TIMEOUT_SECONDS = 2.0
_delivery_failures: set[str] = set()


def notify_games_changed(competition: str) -> bool:
    return _post_update("games", {"competition": competition}, "Live update")


def notify_schedule(snapshot: ScheduleSnapshot) -> bool:
    return _post_update("schedule", snapshot.model_dump(mode="json"), "Schedule report")


def _post_update(path: str, payload: dict, label: str) -> bool:
    api_url = settings.live_update_api_url.rstrip("/")
    secret = settings.live_update_secret
    if not api_url or not secret:
        return False

    for attempt in range(2):
        try:
            response = httpx.post(
                f"{api_url}/internal/updates/{path}",
                headers={"X-Live-Update-Secret": secret},
                json=payload,
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            break
        except Exception as exc:
            transient = isinstance(
                exc,
                (httpx.NetworkError, httpx.TimeoutException, httpx.RemoteProtocolError),
            ) or (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code >= 500
            )
            if attempt == 0 and transient:
                sleep(0.25)
                continue
            if path not in _delivery_failures:
                logger.warning(
                    "%s delivery failed; later failures will be suppressed: %s",
                    label,
                    exc,
                )
            _delivery_failures.add(path)
            return False

    if path in _delivery_failures:
        logger.info("%s delivery recovered", label)
    _delivery_failures.discard(path)
    return True
