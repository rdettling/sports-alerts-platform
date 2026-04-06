from __future__ import annotations

import logging
from datetime import datetime, timezone

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
            alert.metadata_json = {"error": "missing user or game"}
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
        else:
            alert.delivery_status = "failed"
            alert.metadata_json = {"error": f"unsupported delivery_mode={settings.delivery_mode}"}
            failed_count += 1

        alert.sent_at = datetime.now(timezone.utc)

    db.flush()
    return sent_count, failed_count

