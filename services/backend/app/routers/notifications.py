from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import PushSubscription, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.notification import (
    NotificationSettingsOut,
    PushSubscriptionEndpointRequest,
    PushSubscriptionRequest,
    PushSubscriptionStatusOut,
    UpdateNotificationSettingsRequest,
)
from app.services.delivery_settings import delivery_settings

router = APIRouter(tags=["notifications"])


def _settings_out(db: Session, user: User) -> NotificationSettingsOut:
    subscription_count = db.scalar(
        select(func.count(PushSubscription.id)).where(PushSubscription.user_id == user.id)
    ) or 0
    public_key = delivery_settings.vapid_public_key.strip()
    return NotificationSettingsOut(
        email_alerts_enabled=user.email_alerts_enabled,
        push_subscription_count=subscription_count,
        push_configured=bool(public_key and delivery_settings.vapid_private_key.strip()),
        vapid_public_key=public_key or None,
    )


@router.get("/notification-settings", response_model=NotificationSettingsOut)
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsOut:
    return _settings_out(db, current_user)


@router.put("/notification-settings", response_model=NotificationSettingsOut)
def update_notification_settings(
    payload: UpdateNotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsOut:
    current_user.email_alerts_enabled = payload.email_alerts_enabled
    db.commit()
    db.refresh(current_user)
    return _settings_out(db, current_user)


@router.post("/push-subscriptions/status", response_model=PushSubscriptionStatusOut)
def get_push_subscription_status(
    payload: PushSubscriptionEndpointRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PushSubscriptionStatusOut:
    subscription_id = db.scalar(
        select(PushSubscription.id).where(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == str(payload.endpoint),
        )
    )
    return PushSubscriptionStatusOut(is_subscribed=subscription_id is not None)


@router.post("/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def save_push_subscription(
    payload: PushSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not delivery_settings.vapid_public_key.strip() or not delivery_settings.vapid_private_key.strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Push delivery is not configured.")

    endpoint = str(payload.endpoint)
    subscription = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if subscription is None:
        subscription = PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        db.add(subscription)
    else:
        subscription.user_id = current_user.id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_subscription(
    payload: PushSubscriptionEndpointRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == str(payload.endpoint),
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
