from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, UserAlertPreference
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.preference import ALERT_TYPES, AlertPreferenceOut, UpdateAlertPreferenceRequest

router = APIRouter(prefix="/alert-preferences", tags=["alert-preferences"])


def _ensure_default_preferences(db: Session, user_id: int) -> None:
    existing = {
        row.alert_type
        for row in db.scalars(select(UserAlertPreference).where(UserAlertPreference.user_id == user_id)).all()
    }
    for alert_type in ALERT_TYPES:
        if alert_type in existing:
            continue
        db.add(
            UserAlertPreference(
                user_id=user_id,
                alert_type=alert_type,
                is_enabled=True,
                close_game_margin_threshold=5 if alert_type == "close_game_late" else None,
                close_game_time_threshold_seconds=120 if alert_type == "close_game_late" else None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
    db.commit()


@router.get("", response_model=list[AlertPreferenceOut])
def list_alert_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertPreferenceOut]:
    _ensure_default_preferences(db, current_user.id)
    preferences = db.scalars(
        select(UserAlertPreference)
        .where(UserAlertPreference.user_id == current_user.id)
        .order_by(UserAlertPreference.alert_type.asc())
    ).all()
    return [AlertPreferenceOut.model_validate(preference) for preference in preferences]


@router.put("/{alert_type}", response_model=AlertPreferenceOut)
def update_alert_preference(
    alert_type: str,
    payload: UpdateAlertPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertPreferenceOut:
    if alert_type not in ALERT_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert type not found")

    _ensure_default_preferences(db, current_user.id)
    preference = db.scalar(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id == current_user.id,
            UserAlertPreference.alert_type == alert_type,
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
    else:
        preference.close_game_margin_threshold = None
        preference.close_game_time_threshold_seconds = None

    preference.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(preference)
    return AlertPreferenceOut.model_validate(preference)

