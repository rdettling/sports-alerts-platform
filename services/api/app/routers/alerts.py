from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Alert, AlertDelivery, Game, Team, User
from app.db.session import get_db
from app.deps import get_current_user, require_admin_user
from app.schemas.alert import AlertDeliveryOut, AlertHistoryItemOut, AlertHistoryResponse, DevTestAlertRequest, DevTestAlertResponse
from app.services.alert_delivery import deliver_email_alert_now
from app.services.leagues import get_active_leagues, get_alert_types, get_default_test_matchup, get_league_profile

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _resolve_admin_test_teams(db: Session, league: str) -> tuple[Team, Team]:
    teams = db.scalars(select(Team).where(Team.league == league).order_by(Team.id.asc())).all()
    if len(teams) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough teams available for test alerts")

    by_abbr = {team.abbreviation.upper(): team for team in teams}
    default_away_abbr, default_home_abbr = get_default_test_matchup(league)
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
        select(Alert, Game, home_team, away_team)
        .join(Game, Game.id == Alert.game_id)
        .join(home_team, home_team.id == Game.home_team_id)
        .join(away_team, away_team.id == Game.away_team_id)
        .where(Alert.user_id == current_user.id)
        .where(Game.league.in_(active_leagues))
    )
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    if since_hours:
        since_ts = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        stmt = stmt.where(Alert.triggered_at >= since_ts)

    rows = db.execute(stmt.order_by(Alert.triggered_at.desc()).limit(limit)).all()
    alert_ids = [alert.id for alert, _, _, _ in rows]
    deliveries_by_alert: dict[int, list[AlertDeliveryOut]] = {alert_id: [] for alert_id in alert_ids}
    if alert_ids:
        deliveries = db.scalars(
            select(AlertDelivery)
            .where(AlertDelivery.alert_id.in_(alert_ids))
            .order_by(AlertDelivery.alert_id.asc(), AlertDelivery.id.asc())
        ).all()
        for delivery in deliveries:
            deliveries_by_alert[delivery.alert_id].append(
                AlertDeliveryOut(
                    channel=delivery.channel,
                    status=delivery.status,
                    attempted_at=delivery.attempted_at,
                )
            )

    items = [
        AlertHistoryItemOut(
            id=alert.id,
            game_id=alert.game_id,
            alert_type=alert.alert_type,
            triggered_at=alert.triggered_at,
            game_external_id=game.external_game_id,
            home_team_abbreviation=home.abbreviation,
            away_team_abbreviation=away.abbreviation,
            deliveries=deliveries_by_alert[alert.id],
        )
        for alert, game, home, away in rows
    ]
    return AlertHistoryResponse(items=items)


@router.post("/admin/test-email", response_model=DevTestAlertResponse)
def create_admin_test_alert(
    payload: DevTestAlertRequest,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> DevTestAlertResponse:
    league = payload.league.strip().upper()
    try:
        allowed_alert_types = set(get_alert_types(league))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid league") from exc
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
    elif payload.alert_type == "overtime_start":
        game_status = "in_progress"
        home_score = 112
        away_score = 112
        period = 5
        clock = "05:00"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    elif payload.alert_type == "inning_start":
        game_status = "in_progress"
        home_score = 2
        away_score = 1
        period = 7
        clock = "Mid 7th"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    elif payload.alert_type == "extra_innings_start":
        game_status = "in_progress"
        home_score = 3
        away_score = 3
        period = 10
        clock = "Top 10th"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=3)
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
        elif get_league_profile(league).sport == "soccer":
            home_score = 2
            away_score = 1
            period = 2
            clock = "FT"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=4)
    elif payload.alert_type == "score_changed":
        game_status = "in_progress"
        home_score = 0
        away_score = 1
        period = 1
        clock = "18'"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(minutes=25)
    elif payload.alert_type == "second_half_start":
        game_status = "in_progress"
        home_score = 0
        away_score = 0
        period = 2
        clock = "46'"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    elif payload.alert_type == "extra_time_start":
        game_status = "in_progress"
        home_score = 1
        away_score = 1
        period = 3
        clock = "91'"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    elif payload.alert_type == "penalty_kicks":
        game_status = "in_progress"
        home_score = 1
        away_score = 1
        period = 5
        clock = "Pens"
        scheduled_start_time = datetime.now(timezone.utc) - timedelta(hours=2)

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
        is_test=True,
    )
    db.add(target_game)
    db.flush()

    alert = Alert(
        user_id=current_user.id,
        game_id=target_game.id,
        alert_type=payload.alert_type,
        event_key=f"dev-test:{current_user.id}:{target_game.id}:{payload.alert_type}:{uuid4()}",
        event_data=(
            {
                "source": "dev_test",
                "status": game_status,
                "period": period,
                "clock": clock,
                "previous_home_score": 0,
                "previous_away_score": 0,
                "new_home_score": home_score,
                "new_away_score": away_score,
                "scoring_side": "away",
                "is_inferred_goal": True,
            }
            if payload.alert_type == "score_changed"
            else {"source": "dev_test", "status": game_status, "period": period, "clock": clock}
        ),
    )
    db.add(alert)
    db.flush()
    delivery = AlertDelivery(alert_id=alert.id, channel="email", status="pending")
    db.add(delivery)
    db.flush()
    deliver_email_alert_now(
        db,
        alert=alert,
        delivery=delivery,
        user=current_user,
        game=target_game,
        home=home_team,
        away=away_team,
        service="api",
    )
    db.commit()
    db.refresh(alert)
    db.refresh(delivery)
    return DevTestAlertResponse(
        id=alert.id,
        game_id=alert.game_id,
        league=league,
        alert_type=alert.alert_type,
        delivery_status=delivery.status,
    )
