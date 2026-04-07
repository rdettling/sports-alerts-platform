from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Game, SentAlert, Team, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.alert import AlertHistoryItemOut, AlertHistoryResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/history", response_model=AlertHistoryResponse)
def get_alert_history(
    limit: int = Query(default=100, ge=1, le=500),
    alert_type: str | None = Query(default=None),
    since_hours: int | None = Query(default=None, ge=1, le=24 * 30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertHistoryResponse:
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(SentAlert, Game, home_team, away_team)
        .join(Game, Game.id == SentAlert.game_id)
        .join(home_team, home_team.id == Game.home_team_id)
        .join(away_team, away_team.id == Game.away_team_id)
        .where(SentAlert.user_id == current_user.id)
    )
    if alert_type:
        stmt = stmt.where(SentAlert.alert_type == alert_type)
    if since_hours:
        since_ts = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        stmt = stmt.where(SentAlert.sent_at >= since_ts)

    rows = db.execute(stmt.order_by(SentAlert.sent_at.desc()).limit(limit)).all()

    items = [
        AlertHistoryItemOut(
            id=sent_alert.id,
            game_id=sent_alert.game_id,
            alert_type=sent_alert.alert_type,
            delivery_channel=sent_alert.delivery_channel,
            delivery_status=sent_alert.delivery_status,
            sent_at=sent_alert.sent_at,
            provider_message_id=sent_alert.provider_message_id,
            metadata_json=sent_alert.metadata_json,
            game_external_id=game.external_game_id,
            home_team_abbreviation=home.abbreviation,
            away_team_abbreviation=away.abbreviation,
        )
        for sent_alert, game, home, away in rows
    ]
    return AlertHistoryResponse(items=items)
