from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertDelivery, Game, PushSubscription, Team, User
from app.services.delivery_settings import delivery_settings
from app.services.email_templates import build_alert_email_content, build_alert_push_content, build_alert_subject
from app.services.resend import send_resend_email

logger = logging.getLogger(__name__)


def merge_provider_data(delivery: AlertDelivery, updates: dict[str, object]) -> None:
    existing = delivery.provider_data if isinstance(delivery.provider_data, dict) else {}
    delivery.provider_data = {**existing, **updates}


def deliver_email_alert_now(
    db: Session,
    *,
    alert: Alert,
    delivery: AlertDelivery,
    user: User | None,
    game: Game | None,
    home: Team | None,
    away: Team | None,
    service: str,
) -> str:
    delivery.attempted_at = datetime.now(timezone.utc)
    if user is None or game is None:
        delivery.status = "failed"
        merge_provider_data(delivery, {"error": "missing_user_or_game"})
        db.flush()
        return delivery.status

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    if delivery_settings.delivery_mode == "log":
        logger.info(
            "Simulated alert delivery service=%s to=%s subject=%s alert_id=%s body=%s",
            service,
            user.email,
            subject,
            alert.id,
            text_body.replace("\n", " | "),
        )
        delivery.status = "sent"
        delivery.provider_message_id = f"log-{delivery.id}"
        db.flush()
        return delivery.status

    if delivery_settings.delivery_mode != "live":
        delivery.status = "failed"
        merge_provider_data(delivery, {"error": f"unsupported_delivery_mode={delivery_settings.delivery_mode}"})
        db.flush()
        return delivery.status

    result = send_resend_email(
        db,
        service=service,
        to_email=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    if result.sent:
        delivery.status = "sent"
        delivery.provider_message_id = result.provider_message_id
        if result.metadata:
            merge_provider_data(delivery, result.metadata)
        db.flush()
        return delivery.status

    delivery.status = "failed"
    if result.metadata:
        merge_provider_data(delivery, result.metadata)
    db.flush()
    return delivery.status


def deliver_push_alert_now(
    db: Session,
    *,
    alert: Alert,
    delivery: AlertDelivery,
    user: User | None,
    game: Game | None,
    home: Team | None,
    away: Team | None,
    service: str,
) -> str:
    delivery.attempted_at = datetime.now(timezone.utc)
    if user is None or game is None:
        delivery.status = "failed"
        merge_provider_data(delivery, {"error": "missing_user_or_game"})
        db.flush()
        return delivery.status

    subscriptions = db.scalars(
        select(PushSubscription)
        .where(PushSubscription.user_id == user.id)
        .order_by(PushSubscription.id.asc())
    ).all()
    if not subscriptions:
        delivery.status = "failed"
        merge_provider_data(
            delivery,
            {"error": "no_active_subscriptions", "attempted": 0, "sent": 0, "expired": 0},
        )
        db.flush()
        return delivery.status

    if delivery_settings.delivery_mode == "log":
        logger.info(
            "Simulated push delivery service=%s alert_id=%s subscriptions=%s",
            service,
            alert.id,
            len(subscriptions),
        )
        delivery.status = "sent"
        merge_provider_data(
            delivery,
            {"attempted": len(subscriptions), "sent": len(subscriptions), "expired": 0},
        )
        db.flush()
        return delivery.status

    if not delivery_settings.vapid_private_key.strip():
        delivery.status = "failed"
        merge_provider_data(delivery, {"error": "missing_vapid_private_key"})
        db.flush()
        return delivery.status

    title, body = build_alert_push_content(alert, game, home, away)
    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": "/",
            "tag": f"alert-{alert.id}",
        }
    )
    sent = 0
    expired = 0
    errors: list[str] = []
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=delivery_settings.vapid_private_key,
                vapid_claims={"sub": delivery_settings.vapid_subject},
                ttl=300,
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {404, 410}:
                db.delete(subscription)
                expired += 1
            else:
                errors.append(f"http_{status_code}" if status_code else "web_push_error")
        except Exception:
            logger.exception("Unexpected push delivery error service=%s alert_id=%s", service, alert.id)
            errors.append("unexpected_push_error")

    delivery.status = "sent" if sent > 0 else "failed"
    provider_data: dict[str, object] = {
        "attempted": len(subscriptions),
        "sent": sent,
        "expired": expired,
    }
    if errors:
        provider_data["errors"] = errors
    if sent == 0 and not errors and expired > 0:
        provider_data["error"] = "all_subscriptions_expired"
    merge_provider_data(delivery, provider_data)
    db.flush()
    return delivery.status
