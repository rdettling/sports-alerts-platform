from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from time import monotonic

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, SentAlert, Team, User
from app.services.api_usage import record_api_call_event
from worker.config import settings

logger = logging.getLogger(__name__)


ALERT_LABELS = {
    "game_start": "Game start",
    "close_game_late": "Close game late",
    "final_result": "Final result",
}


def _team_abbr(team: Team | None, fallback: str) -> str:
    return (team.abbreviation if team and team.abbreviation else fallback).upper()


def _scoreline(game: Game) -> str:
    if game.away_score is None or game.home_score is None:
        return "—"
    return f"{game.away_score}\u2013{game.home_score}"


def _format_clock(game: Game) -> str:
    raw = (game.clock or "").strip()
    if not raw or raw in {"0", "0.0", "00:00"}:
        return ""
    return raw


def _format_period(game: Game) -> str:
    if game.period is None:
        return ""
    if game.period <= 4:
        return f"Q{game.period}"
    return f"OT{game.period - 4}"


def _primary_status_line(alert: SentAlert, game: Game, away_abbr: str, home_abbr: str) -> str:
    if alert.alert_type == "final_result":
        return f"Final score: {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "game_start":
        return "Tip-off is live now"
    if alert.alert_type == "close_game_late":
        details = [f"{away_abbr} {_scoreline(game)} {home_abbr}"]
        period = _format_period(game)
        clock = _format_clock(game)
        if period:
            details.append(period)
        if clock:
            details.append(f"{clock} left")
        return " \u2022 ".join(details)
    return f"Status: {game.status}"


def _build_subject(alert: SentAlert, game: Game, home: Team | None, away: Team | None) -> str:
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    if alert.alert_type == "final_result":
        return f"[Sports Alerts] Final: {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "game_start":
        return f"[Sports Alerts] Tip-off: {away_abbr} @ {home_abbr}"
    if alert.alert_type == "close_game_late":
        return f"[Sports Alerts] Close Game: {away_abbr} {_scoreline(game)} {home_abbr}"
    return f"[Sports Alerts] {ALERT_LABELS.get(alert.alert_type, 'Alert')}: {away_abbr} @ {home_abbr}"


def _build_email_content(alert: SentAlert, game: Game, home: Team | None, away: Team | None) -> tuple[str, str]:
    home_name = home.name if home else f"Team {game.home_team_id}"
    away_name = away.name if away else f"Team {game.away_team_id}"
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    alert_label = ALERT_LABELS.get(alert.alert_type, alert.alert_type.replace("_", " ").title())
    primary_line = _primary_status_line(alert, game, away_abbr, home_abbr)
    clock = _format_clock(game)
    period = _format_period(game)
    details_parts: list[str] = []
    if game.status:
        details_parts.append(game.status.replace("_", " ").title())
    if period:
        details_parts.append(period)
    if clock:
        details_parts.append(f"{clock} left")
    details_line = " \u2022 ".join(details_parts)
    sent_at = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC")

    return (
        f"Sports Alerts\n"
        f"{alert_label}\n\n"
        f"{away_abbr} @ {home_abbr}\n"
        f"{primary_line}\n"
        f"{away_name} at {home_name}\n"
        f"{details_line}\n"
        f"Sent: {sent_at}\n",
        f"""<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f6f8fc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#121a2f;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #dbe3f1;border-radius:14px;padding:24px;">
            <tr><td style="font-size:14px;font-weight:700;color:#4d5ddb;letter-spacing:0.4px;text-transform:uppercase;">Sports Alerts</td></tr>
            <tr><td style="padding-top:8px;font-size:20px;font-weight:700;color:#121a2f;">{html.escape(alert_label)}</td></tr>
            <tr><td style="padding-top:16px;font-size:28px;font-weight:800;color:#101934;">{html.escape(away_abbr)} @ {html.escape(home_abbr)}</td></tr>
            <tr><td style="padding-top:10px;font-size:18px;font-weight:600;color:#1d2a4d;">{html.escape(primary_line)}</td></tr>
            <tr><td style="padding-top:8px;font-size:15px;color:#5b6784;">{html.escape(away_name)} at {html.escape(home_name)}</td></tr>
            <tr><td style="padding-top:4px;font-size:14px;color:#7c89a8;">{html.escape(details_line)}</td></tr>
            <tr><td style="padding-top:20px;font-size:12px;color:#97a2bd;">Sent {html.escape(sent_at)}</td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>""",
    )


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
        subject = _build_subject(alert, game, home, away)
        text_body, html_body = _build_email_content(alert, game, home, away)

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
