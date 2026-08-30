from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, User, UserAlertPreference, UserGameAlertOverride
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.preference import (
    SUPPORTED_SPORTS,
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
from app.services.competitions import (
    get_active_competitions,
    get_alert_types,
    get_competition_profile,
    get_sport_alert_types,
)

router = APIRouter(prefix="/alert-preferences", tags=["alert-preferences"])


def _validate_sport(sport: str) -> str:
    normalized = sport.lower()
    if normalized not in SUPPORTED_SPORTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sport not found"
        )
    return normalized


def _load_preference(
    db: Session,
    user_id: int,
    sport: str,
    alert_type: str,
) -> UserAlertPreference | None:
    return db.scalar(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id == user_id,
            UserAlertPreference.sport == sport,
            UserAlertPreference.alert_type == alert_type,
        )
    )


def _load_active_game(db: Session, game_id: int) -> Game:
    game = db.get(Game, game_id)
    if not game or game.competition not in set(get_active_competitions(db)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )
    return game


def _validate_game_alert_type(game: Game, alert_type: str) -> None:
    if alert_type not in get_alert_types(game.competition):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found"
        )


def _preference_out(
    sport: str, alert_type: str, preference: UserAlertPreference | None
) -> AlertPreferenceOut:
    settings = resolve_alert_settings(sport, alert_type, preference)
    return AlertPreferenceOut(sport=sport, alert_type=alert_type, **settings.__dict__)


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
    sport = get_competition_profile(game.competition).sport
    preferences = {
        row.alert_type: row
        for row in db.scalars(
            select(UserAlertPreference).where(
                UserAlertPreference.user_id == user_id,
                UserAlertPreference.sport == sport,
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
    for alert_type in get_alert_types(game.competition):
        override = overrides.get(alert_type)
        settings = resolve_alert_settings(
            sport, alert_type, preferences.get(alert_type), override
        )
        items.append(
            GameAlertPreferenceItemOut(
                sport=sport,
                alert_type=alert_type,
                uses_sport_defaults=override is None,
                **settings.__dict__,
            )
        )
    return items


@router.get("", response_model=list[AlertPreferenceGroupOut])
def list_alert_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertPreferenceGroupOut]:
    active_sports = list(
        dict.fromkeys(
            get_competition_profile(competition).sport
            for competition in get_active_competitions(db)
        )
    )
    rows = db.scalars(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id == current_user.id,
            UserAlertPreference.sport.in_(active_sports),
        )
    ).all()
    preferences = {(row.sport, row.alert_type): row for row in rows}
    return [
        AlertPreferenceGroupOut(
            sport=sport,
            preferences=[
                _preference_out(sport, alert_type, preferences.get((sport, alert_type)))
                for alert_type in get_sport_alert_types(sport)
            ],
        )
        for sport in active_sports
    ]


@router.put("/sports/{sport}/{alert_type}", response_model=AlertPreferenceOut)
def update_alert_preference(
    sport: str,
    alert_type: str,
    payload: UpdateAlertSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertPreferenceOut:
    normalized_sport = _validate_sport(sport)
    active_sports = {
        get_competition_profile(competition).sport
        for competition in get_active_competitions(db)
    }
    if normalized_sport not in active_sports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sport not found"
        )
    if alert_type not in get_sport_alert_types(normalized_sport):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found"
        )

    preference = _load_preference(db, current_user.id, normalized_sport, alert_type)
    settings = _settings_from_request(alert_type, payload)
    now = datetime.now(timezone.utc)
    if preference is None:
        preference = UserAlertPreference(
            user_id=current_user.id,
            sport=normalized_sport,
            alert_type=alert_type,
            created_at=now,
        )
    if apply_sparse_overrides(
        preference, settings, default_alert_settings(normalized_sport, alert_type)
    ):
        preference.updated_at = now
        db.add(preference)
    else:
        if preference in db:
            db.delete(preference)
        preference = None

    db.commit()
    return _preference_out(normalized_sport, alert_type, preference)


@router.get("/games/{game_id}", response_model=GameAlertPreferencesOut)
def get_game_alert_preferences(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameAlertPreferencesOut:
    game = _load_active_game(db, game_id)
    sport = get_competition_profile(game.competition).sport
    return GameAlertPreferencesOut(
        game_id=game.id,
        competition=game.competition,
        sport=sport,
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
    game = _load_active_game(db, game_id)
    _validate_game_alert_type(game, alert_type)

    sport = get_competition_profile(game.competition).sport
    preference = _load_preference(db, current_user.id, sport, alert_type)
    sport_settings = resolve_alert_settings(sport, alert_type, preference)
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

    if apply_sparse_overrides(row, settings, sport_settings):
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
    game = _load_active_game(db, game_id)
    _validate_game_alert_type(game, alert_type)

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
