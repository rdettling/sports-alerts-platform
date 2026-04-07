from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, SentAlert, Team, User
from worker.config import settings

logger = logging.getLogger(__name__)


def _build_subject(alert: SentAlert, game: Game, home: Team | None, away: Team | None) -> str:
    matchup = f"{away.abbreviation if away else 'AWAY'} @ {home.abbreviation if home else 'HOME'}"
    return f"[Sports Alerts] {alert.alert_type} - {matchup}"


def _build_body(alert: SentAlert, game: Game, home: Team | None, away: Team | None) -> str:
    home_name = home.name if home else f"team:{game.home_team_id}"
    away_name = away.name if away else f"team:{game.away_team_id}"
    return (
        f"Alert type: {alert.alert_type}\n"
        f"Game: {away_name} at {home_name}\n"
        f"Status: {game.status}\n"
        f"Score: {game.away_score}-{game.home_score}\n"
        f"Time: {game.clock or '-'} Period: {game.period or '-'}\n"
    )


def _merge_metadata(alert: SentAlert, updates: dict[str, object]) -> None:
    existing = alert.metadata_json if isinstance(alert.metadata_json, dict) else {}
    alert.metadata_json = {**existing, **updates}


def _send_email_resend(to_email: str, subject: str, body: str) -> tuple[bool, str | None, dict[str, object] | None]:
    if not settings.resend_api_key:
        return False, None, {"error": "missing_resend_api_key"}

    payload = {
        "from": settings.from_email,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(settings.resend_api_url, json=payload, headers=headers, timeout=15.0)
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
        return False, None, {"error": "resend_http_error", "detail": str(exc)}


def process_pending_alerts(db: Session, limit: int = 100) -> tuple[int, int]:
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
        subject = _build_subject(alert, game, home, away)
        body = _build_body(alert, game, home, away)

        if settings.delivery_mode == "log":
            logger.info(
                "Simulated email delivery to=%s subject=%s alert_id=%s body=%s",
                user.email,
                subject,
                alert.id,
                body.replace("\n", " | "),
            )
            alert.delivery_status = "sent"
            alert.provider_message_id = f"log-{alert.id}"
            sent_count += 1
        elif settings.delivery_mode == "email":
            sent, provider_message_id, error_metadata = _send_email_resend(user.email, subject, body)
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
