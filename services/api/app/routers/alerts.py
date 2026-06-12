from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Game, SentAlert, Team, User, WorkerJob
from app.db.session import get_db
from app.deps import get_current_user, require_admin_user
from app.schemas.alert import AlertHistoryItemOut, AlertHistoryResponse, DevTestAlertRequest, DevTestAlertResponse
from app.services.leagues import ALERT_TYPES_BY_LEAGUE, DEFAULT_TEST_MATCHUPS_BY_LEAGUE, get_active_leagues

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _nudge_delivery_job_now(db: Session) -> None:
    row = db.scalar(select(WorkerJob).where(WorkerJob.job_type == "delivery", WorkerJob.league.is_(None)))
    if row is None or row.status == "running":
        return
    row.status = "queued"
    row.next_run_at = datetime.now(timezone.utc)


def _resolve_admin_test_teams(db: Session, league: str) -> tuple[Team, Team]:
    teams = db.scalars(select(Team).where(Team.league == league).order_by(Team.id.asc())).all()
    if len(teams) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough teams available for test alerts")

    by_abbr = {team.abbreviation.upper(): team for team in teams}
    default_away_abbr, default_home_abbr = DEFAULT_TEST_MATCHUPS_BY_LEAGUE.get(league, ("", ""))
    away = by_abbr.get(default_away_abbr)
    home = by_abbr.get(default_home_abbr)
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
    active_leagues = get_active_leagues(db)
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(SentAlert, Game, home_team, away_team)
        .join(Game, Game.id == SentAlert.game_id)
        .join(home_team, home_team.id == Game.home_team_id)
        .join(away_team, away_team.id == Game.away_team_id)
        .where(SentAlert.user_id == current_user.id)
        .where(Game.league.in_(active_leagues))
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
    league = payload.league.strip().upper()
    allowed_alert_types = set(ALERT_TYPES_BY_LEAGUE.get(league, []))
    if not allowed_alert_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid league")
    if league not in set(get_active_leagues(db)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="League is disabled")
    if payload.alert_type not in allowed_alert_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid alert type '{payload.alert_type}' for league '{league}'",
        )

    away_team, home_team = _resolve_admin_test_teams(db, league)

    game_status = "scheduled"
    home_score = None
    away_score = None
    period = None
    clock = None
    is_final = False
    scheduled_start_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    if payload.alert_type == "close_game_late":
        game_status = "in_progress"
        home_score = 102
        away_score = 100
        period = 4
        clock = "01:42"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    elif payload.alert_type == "inning_start":
        game_status = "in_progress"
        home_score = 2
        away_score = 1
        period = 7
        clock = "Mid 7th"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    elif payload.alert_type == "final_result":
        game_status = "final"
        home_score = 109
        away_score = 105
        is_final = True
        if league == "MLB":
            home_score = 5
            away_score = 3
            period = 9
            clock = "Final"
        elif league == "WORLD_CUP":
            home_score = 2
            away_score = 1
            period = 2
            clock = "FT"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=4)

    target_game = Game(
        external_game_id=f"admin-test-game-{uuid4()}",
        league=league,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        scheduled_start_time=scheduled_start_time,
        status=game_status,
        home_score=home_score,
        away_score=away_score,
        period=period,
        clock=clock,
        is_final=is_final,
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
    _nudge_delivery_job_now(db)
    db.commit()
    db.refresh(sent_alert)
    return DevTestAlertResponse(
        id=sent_alert.id,
        game_id=sent_alert.game_id,
        league=league,
        alert_type=sent_alert.alert_type,
        delivery_status=sent_alert.delivery_status,
    )
