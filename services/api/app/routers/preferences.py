from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Game, User, UserAlertDefault, UserGameAlertOverride
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.preference import (
    ALERT_TYPES_BY_LEAGUE,
    SUPPORTED_LEAGUES,
    AlertPreferenceGroupOut,
    AlertPreferenceOut,
    GameAlertPreferenceItemOut,
    GameAlertPreferencesOut,
    UpdateAlertPreferenceRequest,
    UpdateGameAlertOverrideRequest,
)

router = APIRouter(prefix="/alert-preferences", tags=["alert-preferences"])


def _default_values(alert_type: str) -> tuple[bool, int | None, int | None]:
    if alert_type == "close_game_late":
        return True, 5, 120
    return True, None, None


def _validate_league(league: str) -> str:
    normalized = league.upper()
    if normalized not in SUPPORTED_LEAGUES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    return normalized


def _ensure_default_preferences(db: Session, user_id: int) -> None:
    existing = {
        (row.league, row.alert_type)
        for row in db.scalars(select(UserAlertDefault).where(UserAlertDefault.user_id == user_id)).all()
    }

    now = datetime.now(timezone.utc)
    for league in SUPPORTED_LEAGUES:
        for alert_type in ALERT_TYPES_BY_LEAGUE[league]:
            key = (league, alert_type)
            if key in existing:
                continue
            is_enabled, margin, seconds = _default_values(alert_type)
            inning = 7 if alert_type == "inning_start" else None
            db.add(
                UserAlertDefault(
                    user_id=user_id,
                    league=league,
                    alert_type=alert_type,
                    is_enabled=is_enabled,
                    close_game_margin_threshold=margin,
                    close_game_time_threshold_seconds=seconds,
                    inning_start_threshold=inning,
                    created_at=now,
                    updated_at=now,
                )
            )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _resolve_game_alert_items(db: Session, user_id: int, game: Game) -> list[GameAlertPreferenceItemOut]:
    _ensure_default_preferences(db, user_id)

    defaults = {
        row.alert_type: row
        for row in db.scalars(
            select(UserAlertDefault).where(UserAlertDefault.user_id == user_id, UserAlertDefault.league == game.league)
        ).all()
    }
    overrides = {
        row.alert_type: row
        for row in db.scalars(
            select(UserGameAlertOverride).where(UserGameAlertOverride.user_id == user_id, UserGameAlertOverride.game_id == game.id)
        ).all()
    }

    items: list[GameAlertPreferenceItemOut] = []
    for alert_type in ALERT_TYPES_BY_LEAGUE[game.league]:
        default = defaults.get(alert_type)
        if not default:
            continue
        override = overrides.get(alert_type)

        is_enabled = default.is_enabled
        margin = default.close_game_margin_threshold
        seconds = default.close_game_time_threshold_seconds
        inning = default.inning_start_threshold
        use_league_default = override is None

        if override is not None:
            if override.is_enabled_override is not None:
                is_enabled = override.is_enabled_override
            if alert_type == "close_game_late":
                if override.close_game_margin_threshold_override is not None:
                    margin = override.close_game_margin_threshold_override
                if override.close_game_time_threshold_seconds_override is not None:
                    seconds = override.close_game_time_threshold_seconds_override
            if alert_type == "inning_start" and override.inning_start_threshold_override is not None:
                inning = override.inning_start_threshold_override

        if alert_type != "close_game_late":
            margin = None
            seconds = None
        if alert_type != "inning_start":
            inning = None

        payload: dict[str, int | bool | None] | None = None
        if override is not None:
            payload = {
                "is_enabled_override": override.is_enabled_override,
                "close_game_margin_threshold_override": override.close_game_margin_threshold_override,
                "close_game_time_threshold_seconds_override": override.close_game_time_threshold_seconds_override,
                "inning_start_threshold_override": override.inning_start_threshold_override,
            }

        items.append(
            GameAlertPreferenceItemOut(
                league=game.league,
                alert_type=alert_type,
                use_league_default=use_league_default,
                is_enabled=is_enabled,
                close_game_margin_threshold=margin,
                close_game_time_threshold_seconds=seconds,
                inning_start_threshold=inning,
                override=payload,
            )
        )

    return items


@router.get("", response_model=list[AlertPreferenceGroupOut])
def list_alert_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertPreferenceGroupOut]:
    _ensure_default_preferences(db, current_user.id)
    rows = db.scalars(
        select(UserAlertDefault)
        .where(UserAlertDefault.user_id == current_user.id)
        .order_by(UserAlertDefault.league.asc(), UserAlertDefault.alert_type.asc())
    ).all()

    by_league: dict[str, list[AlertPreferenceOut]] = {league: [] for league in SUPPORTED_LEAGUES}
    for row in rows:
        by_league.setdefault(row.league, []).append(AlertPreferenceOut.model_validate(row))

    return [AlertPreferenceGroupOut(league=league, preferences=by_league.get(league, [])) for league in SUPPORTED_LEAGUES]


@router.put("/leagues/{league}/{alert_type}", response_model=AlertPreferenceOut)
def update_alert_preference(
    league: str,
    alert_type: str,
    payload: UpdateAlertPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertPreferenceOut:
    normalized_league = _validate_league(league)
    if alert_type not in ALERT_TYPES_BY_LEAGUE[normalized_league]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found")

    _ensure_default_preferences(db, current_user.id)
    preference = db.scalar(
        select(UserAlertDefault).where(
            UserAlertDefault.user_id == current_user.id,
            UserAlertDefault.league == normalized_league,
            UserAlertDefault.alert_type == alert_type,
        )
    )
    if not preference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preference not found")

    if payload.is_enabled is not None:
        preference.is_enabled = payload.is_enabled

    if alert_type == "close_game_late":
        if payload.close_game_margin_threshold is not None:
            preference.close_game_margin_threshold = payload.close_game_margin_threshold
        if payload.close_game_time_threshold_seconds is not None:
            preference.close_game_time_threshold_seconds = payload.close_game_time_threshold_seconds
        preference.inning_start_threshold = None
    elif alert_type == "inning_start":
        if payload.inning_start_threshold is not None:
            preference.inning_start_threshold = payload.inning_start_threshold
        preference.close_game_margin_threshold = None
        preference.close_game_time_threshold_seconds = None
    else:
        preference.close_game_margin_threshold = None
        preference.close_game_time_threshold_seconds = None
        preference.inning_start_threshold = None

    preference.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(preference)
    return AlertPreferenceOut.model_validate(preference)


@router.get("/games/{game_id}", response_model=GameAlertPreferencesOut)
def get_game_alert_preferences(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferencesOut:
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    return GameAlertPreferencesOut(game_id=game.id, league=game.league, items=_resolve_game_alert_items(db, current_user.id, game))


@router.put("/games/{game_id}/{alert_type}", response_model=GameAlertPreferenceItemOut)
def update_game_alert_override(
    game_id: int,
    alert_type: str,
    payload: UpdateGameAlertOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferenceItemOut:
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if alert_type not in ALERT_TYPES_BY_LEAGUE[game.league]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found")

    row = db.scalar(
        select(UserGameAlertOverride).where(
            UserGameAlertOverride.user_id == current_user.id,
            UserGameAlertOverride.game_id == game_id,
            UserGameAlertOverride.alert_type == alert_type,
        )
    )
    now = datetime.now(timezone.utc)
    if not row:
        row = UserGameAlertOverride(
            user_id=current_user.id,
            game_id=game_id,
            alert_type=alert_type,
            created_at=now,
            updated_at=now,
        )
        db.add(row)

    row.is_enabled_override = payload.is_enabled_override
    if alert_type == "close_game_late":
        row.close_game_margin_threshold_override = payload.close_game_margin_threshold_override
        row.close_game_time_threshold_seconds_override = payload.close_game_time_threshold_seconds_override
        row.inning_start_threshold_override = None
    elif alert_type == "inning_start":
        row.inning_start_threshold_override = payload.inning_start_threshold_override
        row.close_game_margin_threshold_override = None
        row.close_game_time_threshold_seconds_override = None
    else:
        row.close_game_margin_threshold_override = None
        row.close_game_time_threshold_seconds_override = None
        row.inning_start_threshold_override = None
    row.updated_at = now

    db.commit()

    items = _resolve_game_alert_items(db, current_user.id, game)
    match = next((item for item in items if item.alert_type == alert_type), None)
    if not match:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to resolve override")
    return match


@router.delete("/games/{game_id}/{alert_type}", response_model=GameAlertPreferenceItemOut)
def clear_game_alert_override(
    game_id: int,
    alert_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferenceItemOut:
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if alert_type not in ALERT_TYPES_BY_LEAGUE[game.league]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found")

    row = db.scalar(
        select(UserGameAlertOverride).where(
            UserGameAlertOverride.user_id == current_user.id,
            UserGameAlertOverride.game_id == game_id,
            UserGameAlertOverride.alert_type == alert_type,
        )
    )
    if row:
        db.delete(row)
        db.commit()

    items = _resolve_game_alert_items(db, current_user.id, game)
    match = next((item for item in items if item.alert_type == alert_type), None)
    if not match:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to resolve override")
    return match
