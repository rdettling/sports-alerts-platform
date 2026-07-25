from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertDelivery, Game, PushSubscription, Team, User
from app.services.api_usage import record_api_call_event
from app.services.delivery_settings import delivery_settings
from app.services.email_templates import build_alert_email_content, build_alert_push_content, build_alert_subject

logger = logging.getLogger(__name__)


def merge_provider_data(delivery: AlertDelivery, updates: dict[str, object]) -> None:
    existing = delivery.provider_data if isinstance(delivery.provider_data, dict) else {}
    delivery.provider_data = {**existing, **updates}


def _send_email_resend(
    db: Session,
    *,
    service: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    ingest_run_id: int | None,
) -> tuple[bool, str | None, dict[str, object] | None]:
    if not delivery_settings.resend_api_key:
        return False, None, {"error": "missing_resend_api_key"}

    payload = json.dumps(
        {
            "from": delivery_settings.from_email,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    ).encode("utf-8")
    request = Request(
        delivery_settings.resend_api_url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {delivery_settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "sports-alerts-api/1.0",
        },
    )
    started_at = monotonic()
    try:
        with urlopen(request, timeout=15.0) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read().decode("utf-8")
            record_api_call_event(
                db,
                service=service,
                provider="resend",
                endpoint_key="resend_send_email",
                attempt_status="rate_limited" if status_code == 429 else ("success" if 200 <= status_code < 300 else "error"),
                http_status=status_code,
                latency_ms=int((monotonic() - started_at) * 1000),
                ingest_run_id=ingest_run_id,
                error_code=None if 200 <= status_code < 300 else "resend_request_failed",
            )
            if 200 <= status_code < 300:
                try:
                    provider_id = json.loads(response_body).get("id")
                except json.JSONDecodeError:
                    provider_id = None
                if isinstance(provider_id, str) and provider_id:
                    return True, provider_id, None
                return True, None, {"provider_warning": "missing_message_id"}
            return False, None, {
                "error": "resend_request_failed",
                "status_code": status_code,
                "response_body": response_body[:500],
            }
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        record_api_call_event(
            db,
            service=service,
            provider="resend",
            endpoint_key="resend_send_email",
            attempt_status="rate_limited" if exc.code == 429 else "error",
            http_status=exc.code,
            latency_ms=int((monotonic() - started_at) * 1000),
            ingest_run_id=ingest_run_id,
            error_code="resend_request_failed",
        )
        return False, None, {
            "error": "resend_request_failed",
            "status_code": exc.code,
            "response_body": response_body[:500],
        }
    except URLError as exc:
        record_api_call_event(
            db,
            service=service,
            provider="resend",
            endpoint_key="resend_send_email",
            attempt_status="error",
            latency_ms=int((monotonic() - started_at) * 1000),
            ingest_run_id=ingest_run_id,
            error_code="resend_http_error",
        )
        return False, None, {"error": "resend_http_error", "detail": str(exc.reason)}


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
    ingest_run_id: int | None = None,
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

    sent, provider_message_id, error_metadata = _send_email_resend(
        db,
        service=service,
        to_email=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        ingest_run_id=ingest_run_id,
    )
    if sent:
        delivery.status = "sent"
        delivery.provider_message_id = provider_message_id
        if error_metadata:
            merge_provider_data(delivery, error_metadata)
        db.flush()
        return delivery.status

    delivery.status = "failed"
    if error_metadata:
        merge_provider_data(delivery, error_metadata)
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
