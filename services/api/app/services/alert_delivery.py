from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Game, SentAlert, Team, User
from app.services.api_usage import record_api_call_event
from app.services.email_templates import build_alert_email_content, build_alert_subject

logger = logging.getLogger(__name__)


def merge_alert_metadata(alert: SentAlert, updates: dict[str, object]) -> None:
    existing = alert.metadata_json if isinstance(alert.metadata_json, dict) else {}
    alert.metadata_json = {**existing, **updates}


def _send_email_resend(
    db: Session,
    *,
    service: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    ingest_run_id: int | None,
) -> tuple[bool, str | None, dict[str, object] | None]:
    if not settings.resend_api_key:
        return False, None, {"error": "missing_resend_api_key"}

    payload = json.dumps(
        {
            "from": settings.from_email,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    ).encode("utf-8")
    request = Request(
        settings.resend_api_url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "sports-alerts-api/1.0",
        },
    )
    started_at = monotonic()
    try:
        with urlopen(request, timeout=15.0) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read().decode("utf-8")
            record_api_call_event(
                db,
                service=service,
                provider="resend",
                endpoint_key="resend_send_email",
                attempt_status="rate_limited" if status_code == 429 else ("success" if 200 <= status_code < 300 else "error"),
                http_status=status_code,
                latency_ms=int((monotonic() - started_at) * 1000),
                ingest_run_id=ingest_run_id,
                error_code=None if 200 <= status_code < 300 else "resend_request_failed",
            )
            if 200 <= status_code < 300:
                try:
                    provider_id = json.loads(response_body).get("id")
                except json.JSONDecodeError:
                    provider_id = None
                if isinstance(provider_id, str) and provider_id:
                    return True, provider_id, None
                return True, None, {"provider_warning": "missing_message_id"}
            return False, None, {
                "error": "resend_request_failed",
                "status_code": status_code,
                "response_body": response_body[:500],
            }
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        record_api_call_event(
            db,
            service=service,
            provider="resend",
            endpoint_key="resend_send_email",
            attempt_status="rate_limited" if exc.code == 429 else "error",
            http_status=exc.code,
            latency_ms=int((monotonic() - started_at) * 1000),
            ingest_run_id=ingest_run_id,
            error_code="resend_request_failed",
        )
        return False, None, {
            "error": "resend_request_failed",
            "status_code": exc.code,
            "response_body": response_body[:500],
        }
    except URLError as exc:
        record_api_call_event(
            db,
            service=service,
            provider="resend",
            endpoint_key="resend_send_email",
            attempt_status="error",
            latency_ms=int((monotonic() - started_at) * 1000),
            ingest_run_id=ingest_run_id,
            error_code="resend_http_error",
        )
        return False, None, {"error": "resend_http_error", "detail": str(exc.reason)}


def deliver_alert_now(
    db: Session,
    *,
    alert: SentAlert,
    user: User | None,
    game: Game | None,
    home: Team | None,
    away: Team | None,
    service: str,
    ingest_run_id: int | None = None,
) -> str:
    alert.sent_at = datetime.now(timezone.utc)
    if user is None or game is None:
        alert.delivery_status = "failed"
        merge_alert_metadata(alert, {"error": "missing_user_or_game"})
        db.flush()
        return alert.delivery_status

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    if settings.delivery_mode == "log":
        logger.info(
            "Simulated alert delivery service=%s to=%s subject=%s alert_id=%s body=%s",
            service,
            user.email,
            subject,
            alert.id,
            text_body.replace("\n", " | "),
        )
        alert.delivery_status = "sent"
        alert.provider_message_id = f"log-{alert.id}"
        db.flush()
        return alert.delivery_status

    if settings.delivery_mode != "email":
        alert.delivery_status = "failed"
        merge_alert_metadata(alert, {"error": f"unsupported_delivery_mode={settings.delivery_mode}"})
        db.flush()
        return alert.delivery_status

    sent, provider_message_id, error_metadata = _send_email_resend(
        db,
        service=service,
        to_email=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        ingest_run_id=ingest_run_id,
    )
    if sent:
        alert.delivery_status = "sent"
        alert.provider_message_id = provider_message_id
        if error_metadata:
            merge_alert_metadata(alert, error_metadata)
        db.flush()
        return alert.delivery_status

    alert.delivery_status = "failed"
    if error_metadata:
        merge_alert_metadata(alert, error_metadata)
    db.flush()
    return alert.delivery_status
