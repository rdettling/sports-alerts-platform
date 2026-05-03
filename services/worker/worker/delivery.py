from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import monotonic

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Game, SentAlert, Team, User
from app.services.api_usage import record_api_call_event
from app.services.email_templates import build_alert_email_content, build_alert_subject
from worker.config import settings

logger = logging.getLogger(__name__)


def _merge_metadata(alert: SentAlert, updates: dict[str, object]) -> None:
    existing = alert.metadata_json if isinstance(alert.metadata_json, dict) else {}
    alert.metadata_json = {**existing, **updates}


def _send_email_resend(
    db: Session,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    ingest_run_id: int | None = None,
) -> tuple[bool, str | None, dict[str, object] | None]:
    if not settings.resend_api_key:
        return False, None, {"error": "missing_resend_api_key"}

    payload = {
        "from": settings.from_email,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    started_at = monotonic()
    try:
        response = httpx.post(settings.resend_api_url, json=payload, headers=headers, timeout=15.0)
        record_api_call_event(
            db,
            service="worker",
            provider="resend",
            endpoint_key="resend_send_email",
            attempt_status="rate_limited"
            if response.status_code == 429
            else ("success" if response.is_success else "error"),
            http_status=response.status_code,
            latency_ms=int((monotonic() - started_at) * 1000),
            ingest_run_id=ingest_run_id,
            error_code=None if response.is_success else "resend_request_failed",
        )
        if response.is_success:
            body_json = response.json()
            provider_id = body_json.get("id")
            if isinstance(provider_id, str) and provider_id:
                return True, provider_id, None
            return True, None, {"provider_warning": "missing_message_id"}

        return (
            False,
            None,
            {
                "error": "resend_request_failed",
                "status_code": response.status_code,
                "response_body": response.text[:500],
            },
        )
    except httpx.HTTPError as exc:
        record_api_call_event(
            db,
            service="worker",
            provider="resend",
            endpoint_key="resend_send_email",
            attempt_status="error",
            latency_ms=int((monotonic() - started_at) * 1000),
            ingest_run_id=ingest_run_id,
            error_code="resend_http_error",
        )
        return False, None, {"error": "resend_http_error", "detail": str(exc)}


def process_pending_alerts(db: Session, limit: int = 100, ingest_run_id: int | None = None) -> tuple[int, int]:
    pending = db.scalars(
        select(SentAlert)
        .where(SentAlert.delivery_status == "pending")
        .order_by(SentAlert.sent_at.asc())
        .limit(limit)
    ).all()
    sent_count = 0
    failed_count = 0

    for alert in pending:
        user = db.get(User, alert.user_id)
        game = db.get(Game, alert.game_id)
        if not user or not game:
            alert.delivery_status = "failed"
            _merge_metadata(alert, {"error": "missing user or game"})
            failed_count += 1
            continue

        home = db.get(Team, game.home_team_id)
        away = db.get(Team, game.away_team_id)
        subject = build_alert_subject(alert, game, home, away)
        text_body, html_body = build_alert_email_content(alert, game, home, away)

        if settings.delivery_mode == "log":
            logger.info(
                "Simulated email delivery to=%s subject=%s alert_id=%s body=%s",
                user.email,
                subject,
                alert.id,
                text_body.replace("\n", " | "),
            )
            alert.delivery_status = "sent"
            alert.provider_message_id = f"log-{alert.id}"
            sent_count += 1
        elif settings.delivery_mode == "email":
            sent, provider_message_id, error_metadata = _send_email_resend(
                db,
                user.email,
                subject,
                text_body,
                html_body,
                ingest_run_id=ingest_run_id,
            )
            if sent:
                alert.delivery_status = "sent"
                alert.provider_message_id = provider_message_id
                if error_metadata:
                    _merge_metadata(alert, error_metadata)
                sent_count += 1
            else:
                alert.delivery_status = "failed"
                if error_metadata:
                    _merge_metadata(alert, error_metadata)
                failed_count += 1
        else:
            alert.delivery_status = "failed"
            _merge_metadata(alert, {"error": f"unsupported delivery_mode={settings.delivery_mode}"})
            failed_count += 1

        alert.sent_at = datetime.now(timezone.utc)

    db.flush()
    return sent_count, failed_count


def count_pending_alerts(db: Session) -> int:
    return db.scalar(
        select(func.count(SentAlert.id)).where(SentAlert.delivery_status == "pending")
    ) or 0
