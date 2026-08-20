from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Alert, AlertDelivery, Game, Team, User
from app.db.session import get_db
from app.deps import get_current_user, require_admin_user
from app.schemas.alert import (
    AdminTestAlertRequest,
    AdminTestAlertResponse,
    AlertDeliveryOut,
    AlertHistoryItemOut,
    AlertHistoryResponse,
)
from app.services.alert_delivery import deliver_email_alert_now, deliver_push_alert_now
from app.services.competitions import competition_teams_query, get_active_competitions, get_alert_types, get_competition_profile

router = APIRouter(prefix="/alerts", tags=["alerts"])


@dataclass(frozen=True)
class AdminTestGameState:
    status: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    start_offset: timedelta
    is_final: bool = False


ADMIN_TEST_GAME_STATES = {
    "game_start": AdminTestGameState("scheduled", None, None, None, None, timedelta(minutes=30)),
    "close_game_late": AdminTestGameState("in_progress", 102, 100, 4, "01:42", -timedelta(hours=2)),
    "overtime_start": AdminTestGameState("in_progress", 112, 112, 5, "05:00", -timedelta(hours=2)),
    "inning_start": AdminTestGameState("in_progress", 2, 1, 7, "Mid 7th", -timedelta(hours=2)),
    "extra_innings_start": AdminTestGameState("in_progress", 3, 3, 10, "Top 10th", -timedelta(hours=3)),
    "second_half_start": AdminTestGameState("in_progress", 0, 0, 2, "46'", -timedelta(hours=1)),
    "extra_time_start": AdminTestGameState("in_progress", 1, 1, 3, "91'", -timedelta(hours=2)),
    "penalty_kicks": AdminTestGameState("in_progress", 1, 1, 5, "Pens", -timedelta(hours=2)),
    "score_changed": AdminTestGameState("in_progress", 0, 1, 1, "18'", -timedelta(minutes=25)),
    "final_result": AdminTestGameState("final", 109, 105, None, None, -timedelta(hours=4), True),
}

ADMIN_TEST_SPORT_OVERRIDES = {
    ("football", "close_game_late"): AdminTestGameState(
        "in_progress", 20, 17, 4, "04:30", -timedelta(hours=2)
    ),
    ("football", "overtime_start"): AdminTestGameState(
        "in_progress", 20, 20, 5, "10:00", -timedelta(hours=2)
    ),
    ("football", "final_result"): AdminTestGameState(
        "final", 24, 21, 4, "0:00", -timedelta(hours=4), True
    ),
    ("baseball", "final_result"): AdminTestGameState(
        "final", 5, 3, 9, "Final", -timedelta(hours=4), True
    ),
    ("soccer", "final_result"): AdminTestGameState(
        "final", 2, 1, 2, "FT", -timedelta(hours=4), True
    ),
}


def _resolve_admin_test_teams(db: Session, competition: str) -> tuple[Team, Team]:
    teams = db.scalars(competition_teams_query(competition).order_by(Team.id.asc()).limit(2)).all()
    if len(teams) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough teams available for test alerts")
    return teams[0], teams[1]


def _build_admin_test_objects(
    *,
    user_id: int,
    competition: str,
    alert_type: str,
    away_team: Team,
    home_team: Team,
) -> tuple[Game, Alert]:
    sport = get_competition_profile(competition).sport
    state = ADMIN_TEST_SPORT_OVERRIDES.get((sport, alert_type), ADMIN_TEST_GAME_STATES[alert_type])
    game = Game(
        id=0,
        external_game_id="admin-test",
        competition=competition,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        scheduled_start_time=datetime.now(timezone.utc) + state.start_offset,
        status=state.status,
        home_score=state.home_score,
        away_score=state.away_score,
        period=state.period,
        clock=state.clock,
        is_final=state.is_final,
    )
    event_data: dict[str, object] = {
        "status": state.status,
        "period": state.period,
        "clock": state.clock,
    }
    if alert_type == "score_changed":
        event_data.update(
            previous_home_score=0,
            previous_away_score=0,
            new_home_score=state.home_score,
            new_away_score=state.away_score,
            scoring_side="away",
            is_inferred_goal=True,
        )
    return game, Alert(
        id=0,
        user_id=user_id,
        game_id=0,
        alert_type=alert_type,
        event_key="admin-test",
        event_data=event_data,
    )


@router.get("/history", response_model=AlertHistoryResponse)
def get_alert_history(
    limit: int = Query(default=100, ge=1, le=500),
    alert_type: str | None = Query(default=None),
    since_hours: int | None = Query(default=None, ge=1, le=24 * 30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertHistoryResponse:
    active_competitions = get_active_competitions(db)
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(Alert, Game, home_team, away_team)
        .join(Game, Game.id == Alert.game_id)
        .join(home_team, home_team.id == Game.home_team_id)
        .join(away_team, away_team.id == Game.away_team_id)
        .where(Alert.user_id == current_user.id)
        .where(Game.competition.in_(active_competitions))
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


@router.post("/admin/test", response_model=AdminTestAlertResponse)
def create_admin_test_alert(
    payload: AdminTestAlertRequest,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> AdminTestAlertResponse:
    competition = payload.competition.strip().upper()
    try:
        allowed_alert_types = set(get_alert_types(competition))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid competition") from exc
    if not allowed_alert_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid competition")
    if competition not in set(get_active_competitions(db)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Competition is disabled")
    if payload.alert_type not in allowed_alert_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid alert type '{payload.alert_type}' for competition '{competition}'",
        )

    away_team, home_team = _resolve_admin_test_teams(db, competition)
    target_game, alert = _build_admin_test_objects(
        user_id=current_user.id,
        competition=competition,
        alert_type=payload.alert_type,
        away_team=away_team,
        home_team=home_team,
    )
    deliveries: list[AlertDelivery] = []
    if current_user.alert_delivery_mode in {"email", "both"}:
        email_delivery = AlertDelivery(id=0, alert_id=0, channel="email", status="pending")
        deliver_email_alert_now(
            db,
            alert=alert,
            delivery=email_delivery,
            user=current_user,
            game=target_game,
            home=home_team,
            away=away_team,
            service="api-test",
        )
        deliveries.append(email_delivery)
    if current_user.alert_delivery_mode in {"push", "both"}:
        push_delivery = AlertDelivery(id=0, alert_id=0, channel="push", status="pending")
        deliver_push_alert_now(
            db,
            alert=alert,
            delivery=push_delivery,
            user=current_user,
            game=target_game,
            home=home_team,
            away=away_team,
            service="api-test",
        )
        deliveries.append(push_delivery)
    db.commit()
    return AdminTestAlertResponse(
        competition=competition,
        alert_type=payload.alert_type,
        deliveries=[
            AlertDeliveryOut(
                channel=delivery.channel,
                status=delivery.status,
                attempted_at=delivery.attempted_at,
            )
            for delivery in deliveries
        ],
    )
