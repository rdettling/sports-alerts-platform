from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from pywebpush import WebPushException, webpush

from app.db.models import Alert, Game, PushSubscription, Team, User
from app.services.alert_content import build_alert_email_content, build_alert_push_content, build_alert_subject
from app.services.delivery_settings import delivery_settings
from app.services.resend import send_resend_email

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailAlertPayload:
    alert_id: int
    delivery_id: int
    service: str
    to_email: str
    subject: str
    text_body: str
    html_body: str


@dataclass(frozen=True)
class PushSubscriptionPayload:
    id: int
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class PushAlertPayload:
    alert_id: int
    service: str
    title: str
    body: str
    subscriptions: tuple[PushSubscriptionPayload, ...]


@dataclass(frozen=True)
class DeliveryOutcome:
    status: str
    provider_message_id: str | None = None
    provider_data: dict[str, object] = field(default_factory=dict)
    expired_subscription_ids: tuple[int, ...] = ()


def build_email_payload(
    *,
    alert: Alert,
    delivery_id: int,
    user: User,
    game: Game,
    home: Team | None,
    away: Team | None,
    service: str,
) -> EmailAlertPayload:
    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)
    return EmailAlertPayload(
        alert_id=alert.id,
        delivery_id=delivery_id,
        service=service,
        to_email=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def build_push_payload(
    *,
    alert: Alert,
    game: Game,
    home: Team | None,
    away: Team | None,
    subscriptions: list[PushSubscription],
    service: str,
) -> PushAlertPayload:
    title, body = build_alert_push_content(alert, game, home, away)
    return PushAlertPayload(
        alert_id=alert.id,
        service=service,
        title=title,
        body=body,
        subscriptions=tuple(
            PushSubscriptionPayload(
                id=subscription.id,
                endpoint=subscription.endpoint,
                p256dh=subscription.p256dh,
                auth=subscription.auth,
            )
            for subscription in subscriptions
        ),
    )


def _log_email_failure(*, payload: EmailAlertPayload, metadata: dict[str, object]) -> None:
    logger.warning(
        "Alert email delivery failed service=%s alert_id=%s error=%s status_code=%s",
        payload.service,
        payload.alert_id,
        metadata.get("error", "unknown_error"),
        metadata.get("status_code"),
    )


def send_email_alert(payload: EmailAlertPayload) -> DeliveryOutcome:
    if delivery_settings.delivery_mode == "log":
        logger.info(
            "Simulated alert delivery service=%s to=%s subject=%s alert_id=%s body=%s",
            payload.service,
            payload.to_email,
            payload.subject,
            payload.alert_id,
            payload.text_body.replace("\n", " | "),
        )
        return DeliveryOutcome(status="sent", provider_message_id=f"log-{payload.delivery_id}")

    if delivery_settings.delivery_mode != "live":
        metadata = {"error": f"unsupported_delivery_mode={delivery_settings.delivery_mode}"}
        _log_email_failure(payload=payload, metadata=metadata)
        return DeliveryOutcome(status="failed", provider_data=metadata)

    result = send_resend_email(
        to_email=payload.to_email,
        subject=payload.subject,
        text_body=payload.text_body,
        html_body=payload.html_body,
    )
    metadata = result.metadata or {}
    if result.sent:
        return DeliveryOutcome(
            status="sent",
            provider_message_id=result.provider_message_id,
            provider_data=metadata,
        )

    _log_email_failure(payload=payload, metadata=metadata)
    return DeliveryOutcome(status="failed", provider_data=metadata)


def send_push_alert(payload: PushAlertPayload) -> DeliveryOutcome:
    if not payload.subscriptions:
        return DeliveryOutcome(
            status="failed",
            provider_data={"error": "no_active_subscriptions", "attempted": 0, "sent": 0, "expired": 0},
        )

    if delivery_settings.delivery_mode == "log":
        logger.info(
            "Simulated push delivery service=%s alert_id=%s subscriptions=%s",
            payload.service,
            payload.alert_id,
            len(payload.subscriptions),
        )
        return DeliveryOutcome(
            status="sent",
            provider_data={
                "attempted": len(payload.subscriptions),
                "sent": len(payload.subscriptions),
                "expired": 0,
            },
        )

    if delivery_settings.delivery_mode != "live":
        return DeliveryOutcome(
            status="failed",
            provider_data={
                "error": f"unsupported_delivery_mode={delivery_settings.delivery_mode}"
            },
        )

    if not delivery_settings.vapid_private_key.strip():
        return DeliveryOutcome(status="failed", provider_data={"error": "missing_vapid_private_key"})

    data = json.dumps(
        {
            "title": payload.title,
            "body": payload.body,
            "url": "/",
            "tag": f"alert-{payload.alert_id}",
        }
    )
    sent = 0
    expired_ids: list[int] = []
    errors: list[str] = []
    for subscription in payload.subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=data,
                vapid_private_key=delivery_settings.vapid_private_key,
                vapid_claims={"sub": delivery_settings.vapid_subject},
                ttl=300,
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {404, 410}:
                expired_ids.append(subscription.id)
            else:
                errors.append(f"http_{status_code}" if status_code else "web_push_error")
        except Exception:
            logger.exception(
                "Unexpected push delivery error service=%s alert_id=%s",
                payload.service,
                payload.alert_id,
            )
            errors.append("unexpected_push_error")

    provider_data: dict[str, object] = {
        "attempted": len(payload.subscriptions),
        "sent": sent,
        "expired": len(expired_ids),
    }
    if errors:
        provider_data["errors"] = errors
    if sent == 0 and not errors and expired_ids:
        provider_data["error"] = "all_subscriptions_expired"
    return DeliveryOutcome(
        status="sent" if sent > 0 else "failed",
        provider_data=provider_data,
        expired_subscription_ids=tuple(expired_ids),
    )
