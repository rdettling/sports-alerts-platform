from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, User, UserAlertPreference, UserGameAlertOverride
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.preference import (
    SUPPORTED_LEAGUES,
    AlertPreferenceGroupOut,
    AlertPreferenceOut,
    GameAlertPreferenceItemOut,
    GameAlertPreferencesOut,
    UpdateAlertSettingsRequest,
)
from app.services.alert_preferences import (
    AlertSettings,
    apply_sparse_overrides,
    default_alert_settings,
    resolve_alert_settings,
)
from app.services.leagues import get_active_leagues, get_alert_types

router = APIRouter(prefix="/alert-preferences", tags=["alert-preferences"])


def _validate_league(league: str) -> str:
    normalized = league.upper()
    if normalized not in SUPPORTED_LEAGUES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="League not found"
        )
    return normalized


def _load_preference(
    db: Session,
    user_id: int,
    league: str,
    alert_type: str,
) -> UserAlertPreference | None:
    return db.scalar(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id == user_id,
            UserAlertPreference.league == league,
            UserAlertPreference.alert_type == alert_type,
        )
    )


def _preference_out(
    league: str, alert_type: str, preference: UserAlertPreference | None
) -> AlertPreferenceOut:
    settings = resolve_alert_settings(league, alert_type, preference)
    return AlertPreferenceOut(league=league, alert_type=alert_type, **settings.__dict__)


def _settings_from_request(
    alert_type: str, payload: UpdateAlertSettingsRequest
) -> AlertSettings:
    close_fields = (
        payload.close_game_margin_threshold,
        payload.close_game_time_threshold_seconds,
    )
    if alert_type == "close_game_late":
        if any(value is None for value in close_fields):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Close-game alerts require margin and time thresholds",
            )
        if payload.inning_start_threshold is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Inning threshold is not supported",
            )
        return AlertSettings(
            is_enabled=payload.is_enabled,
            close_game_margin_threshold=payload.close_game_margin_threshold,
            close_game_time_threshold_seconds=payload.close_game_time_threshold_seconds,
        )
    if alert_type == "inning_start":
        if payload.inning_start_threshold is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Inning alerts require a threshold",
            )
        if any(value is not None for value in close_fields):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Close-game thresholds are not supported",
            )
        return AlertSettings(
            is_enabled=payload.is_enabled,
            inning_start_threshold=payload.inning_start_threshold,
        )
    if any(
        value is not None for value in (*close_fields, payload.inning_start_threshold)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thresholds are not supported",
        )
    return AlertSettings(is_enabled=payload.is_enabled)


def _resolve_game_alert_items(
    db: Session, user_id: int, game: Game
) -> list[GameAlertPreferenceItemOut]:
    preferences = {
        row.alert_type: row
        for row in db.scalars(
            select(UserAlertPreference).where(
                UserAlertPreference.user_id == user_id,
                UserAlertPreference.league == game.league,
            )
        ).all()
    }
    overrides = {
        row.alert_type: row
        for row in db.scalars(
            select(UserGameAlertOverride).where(
                UserGameAlertOverride.user_id == user_id,
                UserGameAlertOverride.game_id == game.id,
            )
        ).all()
    }

    items: list[GameAlertPreferenceItemOut] = []
    for alert_type in get_alert_types(game.league):
        override = overrides.get(alert_type)
        settings = resolve_alert_settings(
            game.league, alert_type, preferences.get(alert_type), override
        )
        items.append(
            GameAlertPreferenceItemOut(
                league=game.league,
                alert_type=alert_type,
                uses_league_defaults=override is None,
                **settings.__dict__,
            )
        )
    return items


@router.get("", response_model=list[AlertPreferenceGroupOut])
def list_alert_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertPreferenceGroupOut]:
    active_leagues = get_active_leagues(db)
    rows = db.scalars(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id == current_user.id,
            UserAlertPreference.league.in_(active_leagues),
        )
    ).all()
    preferences = {(row.league, row.alert_type): row for row in rows}
    return [
        AlertPreferenceGroupOut(
            league=league,
            preferences=[
                _preference_out(
                    league, alert_type, preferences.get((league, alert_type))
                )
                for alert_type in get_alert_types(league)
            ],
        )
        for league in active_leagues
    ]


@router.put("/leagues/{league}/{alert_type}", response_model=AlertPreferenceOut)
def update_alert_preference(
    league: str,
    alert_type: str,
    payload: UpdateAlertSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertPreferenceOut:
    normalized_league = _validate_league(league)
    if normalized_league not in set(get_active_leagues(db)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="League not found"
        )
    if alert_type not in get_alert_types(normalized_league):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found"
        )

    preference = _load_preference(db, current_user.id, normalized_league, alert_type)
    settings = _settings_from_request(alert_type, payload)
    now = datetime.now(timezone.utc)
    if preference is None:
        preference = UserAlertPreference(
            user_id=current_user.id,
            league=normalized_league,
            alert_type=alert_type,
            created_at=now,
        )
    if apply_sparse_overrides(
        preference, settings, default_alert_settings(normalized_league, alert_type)
    ):
        preference.updated_at = now
        db.add(preference)
    else:
        if preference in db:
            db.delete(preference)
        preference = None

    db.commit()
    return _preference_out(normalized_league, alert_type, preference)


@router.get("/games/{game_id}", response_model=GameAlertPreferencesOut)
def get_game_alert_preferences(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferencesOut:
    game = db.get(Game, game_id)
    if not game or game.league not in set(get_active_leagues(db)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )
    return GameAlertPreferencesOut(
        game_id=game.id,
        league=game.league,
        items=_resolve_game_alert_items(db, current_user.id, game),
    )


@router.put("/games/{game_id}/{alert_type}", response_model=GameAlertPreferenceItemOut)
def update_game_alert_settings(
    game_id: int,
    alert_type: str,
    payload: UpdateAlertSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferenceItemOut:
    game = db.get(Game, game_id)
    if not game or game.league not in set(get_active_leagues(db)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )
    if alert_type not in get_alert_types(game.league):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found"
        )

    preference = _load_preference(db, current_user.id, game.league, alert_type)
    league_settings = resolve_alert_settings(game.league, alert_type, preference)
    settings = _settings_from_request(alert_type, payload)
    row = db.scalar(
        select(UserGameAlertOverride).where(
            UserGameAlertOverride.user_id == current_user.id,
            UserGameAlertOverride.game_id == game_id,
            UserGameAlertOverride.alert_type == alert_type,
        )
    )
    now = datetime.now(timezone.utc)
    if row is None:
        row = UserGameAlertOverride(
            user_id=current_user.id,
            game_id=game_id,
            alert_type=alert_type,
            created_at=now,
            updated_at=now,
        )

    if apply_sparse_overrides(row, settings, league_settings):
        row.updated_at = now
        db.add(row)
    elif row in db:
        db.delete(row)
    db.commit()

    return next(
        item
        for item in _resolve_game_alert_items(db, current_user.id, game)
        if item.alert_type == alert_type
    )


@router.delete(
    "/games/{game_id}/{alert_type}", response_model=GameAlertPreferenceItemOut
)
def reset_game_alert_settings(
    game_id: int,
    alert_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferenceItemOut:
    game = db.get(Game, game_id)
    if not game or game.league not in set(get_active_leagues(db)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )
    if alert_type not in get_alert_types(game.league):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found"
        )

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

    return next(
        item
        for item in _resolve_game_alert_items(db, current_user.id, game)
        if item.alert_type == alert_type
    )
