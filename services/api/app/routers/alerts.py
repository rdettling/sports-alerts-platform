from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Game, SentAlert, Team, User
from app.db.session import get_db
from app.deps import get_current_user, require_admin_user
from app.schemas.alert import AlertHistoryItemOut, AlertHistoryResponse, DevTestAlertRequest, DevTestAlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])
DEFAULT_TEST_AWAY_ABBR = "ATL"
DEFAULT_TEST_HOME_ABBR = "BOS"


def _resolve_admin_test_teams(db: Session) -> tuple[Team, Team]:
    teams = db.scalars(select(Team).order_by(Team.id.asc())).all()
    if len(teams) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough teams available for test alerts")

    by_abbr = {team.abbreviation.upper(): team for team in teams}
    away = by_abbr.get(DEFAULT_TEST_AWAY_ABBR)
    home = by_abbr.get(DEFAULT_TEST_HOME_ABBR)
    if away and home and away.id != home.id:
        return away, home
    return teams[0], teams[1]


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


@router.post("/admin/test-email", response_model=DevTestAlertResponse)
def create_admin_test_alert(
    payload: DevTestAlertRequest,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> DevTestAlertResponse:
    allowed_alert_types = {"game_start", "close_game_late", "final_result"}
    if payload.alert_type not in allowed_alert_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid alert type")

    away_team, home_team = _resolve_admin_test_teams(db)
    target_game = Game(
        external_game_id=f"admin-test-game-{uuid4()}",
        league="NBA",
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        scheduled_start_time=datetime.now(timezone.utc) + timedelta(minutes=30),
        status="scheduled",
        home_score=None,
        away_score=None,
        period=None,
        clock=None,
        is_final=False,
    )
    db.add(target_game)
    db.flush()

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
