from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.db.models import Game, SentAlert, Team, User, UserGameFollow
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.alert import AlertHistoryItemOut, AlertHistoryResponse, DevTestAlertRequest, DevTestAlertResponse

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


@router.post("/dev/test-email", response_model=DevTestAlertResponse)
def create_dev_test_alert(
    payload: DevTestAlertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DevTestAlertResponse:
    if not settings.dev_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    allowed_alert_types = {"game_start", "close_game_late", "final_result"}
    if payload.alert_type not in allowed_alert_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid alert type")

    target_game: Game | None = None
    if payload.game_id is not None:
        target_game = db.get(Game, payload.game_id)
        if not target_game:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    else:
        followed_game_id = db.scalar(
            select(UserGameFollow.game_id)
            .where(UserGameFollow.user_id == current_user.id)
            .order_by(UserGameFollow.id.desc())
            .limit(1)
        )
        if followed_game_id:
            target_game = db.get(Game, followed_game_id)
        if not target_game:
            target_game = db.scalar(select(Game).order_by(Game.scheduled_start_time.asc()).limit(1))

    if not target_game:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No games available to create test alert")

    sent_alert = SentAlert(
        user_id=current_user.id,
        game_id=target_game.id,
        alert_type=payload.alert_type,
        delivery_channel="email",
        delivery_status="pending",
        sent_at=datetime.now(timezone.utc),
        dedupe_key=f"dev-test:{current_user.id}:{target_game.id}:{payload.alert_type}:{uuid4()}",
        metadata_json={"source": "dev_test"},
    )
    db.add(sent_alert)
    db.commit()
    db.refresh(sent_alert)
    return DevTestAlertResponse(
        id=sent_alert.id,
        game_id=sent_alert.game_id,
        alert_type=sent_alert.alert_type,
        delivery_status=sent_alert.delivery_status,
    )
