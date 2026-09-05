from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.db.models import AlertDelivery, Game, PushSubscription, Team, User
from app.db.session import SessionLocal
from app.db.usage import database_source
from app.services.alert_delivery import (
    DeliveryOutcome,
    EmailAlertPayload,
    PushAlertPayload,
    build_email_payload,
    build_push_payload,
    send_email_alert,
    send_push_alert,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimedDelivery:
    id: int
    payload: EmailAlertPayload | PushAlertPayload | None


@dataclass(frozen=True)
class DrainResult:
    recovered: int = 0
    sent: int = 0
    failed: int = 0


def _merge_provider_data(existing: object, updates: dict[str, object]) -> dict[str, object]:
    current = existing if isinstance(existing, dict) else {}
    return {**current, **updates}


def _recover_interrupted_deliveries() -> int:
    with SessionLocal() as db:
        rows = db.scalars(
            select(AlertDelivery).where(
                AlertDelivery.status == "pending",
                AlertDelivery.attempted_at.is_not(None),
            )
        ).all()
        for delivery in rows:
            delivery.status = "failed"
            delivery.provider_data = _merge_provider_data(
                delivery.provider_data,
                {"error": "interrupted_during_delivery"},
            )
        db.commit()
        return len(rows)


def _claim_next_delivery() -> ClaimedDelivery | None:
    with SessionLocal() as db:
        delivery = db.scalar(
            select(AlertDelivery)
            .where(
                AlertDelivery.status == "pending",
                AlertDelivery.attempted_at.is_(None),
            )
            .order_by(AlertDelivery.id.asc())
            .limit(1)
        )
        if delivery is None:
            return None

        attempted_at = datetime.now(timezone.utc)
        alert = delivery.alert
        user = db.get(User, alert.user_id) if alert else None
        game = db.get(Game, alert.game_id) if alert else None
        if alert is None or user is None or game is None:
            delivery.attempted_at = attempted_at
            delivery.status = "failed"
            delivery.provider_data = _merge_provider_data(
                delivery.provider_data,
                {"error": "missing_alert_user_or_game"},
            )
            delivery_id = delivery.id
            db.commit()
            return ClaimedDelivery(id=delivery_id, payload=None)

        home = db.get(Team, game.home_team_id)
        away = db.get(Team, game.away_team_id)
        try:
            if delivery.channel == "email":
                payload: EmailAlertPayload | PushAlertPayload = build_email_payload(
                    alert=alert,
                    delivery_id=delivery.id,
                    user=user,
                    game=game,
                    home=home,
                    away=away,
                    service="worker",
                )
            elif delivery.channel == "push":
                subscriptions = db.scalars(
                    select(PushSubscription)
                    .where(PushSubscription.user_id == user.id)
                    .order_by(PushSubscription.id.asc())
                ).all()
                payload = build_push_payload(
                    alert=alert,
                    game=game,
                    home=home,
                    away=away,
                    subscriptions=list(subscriptions),
                    service="worker",
                )
            else:
                delivery.attempted_at = attempted_at
                delivery.status = "failed"
                delivery.provider_data = _merge_provider_data(
                    delivery.provider_data,
                    {"error": f"unsupported_channel={delivery.channel}"},
                )
                delivery_id = delivery.id
                db.commit()
                return ClaimedDelivery(id=delivery_id, payload=None)
        except Exception:
            logger.exception("Failed to prepare alert delivery delivery_id=%s", delivery.id)
            delivery.attempted_at = attempted_at
            delivery.status = "failed"
            delivery.provider_data = _merge_provider_data(
                delivery.provider_data,
                {"error": "payload_preparation_failed"},
            )
            delivery_id = delivery.id
            db.commit()
            return ClaimedDelivery(id=delivery_id, payload=None)

        delivery.attempted_at = attempted_at
        delivery_id = delivery.id
        db.commit()
        return ClaimedDelivery(id=delivery_id, payload=payload)


def _save_outcome(delivery_id: int, outcome: DeliveryOutcome) -> None:
    with SessionLocal() as db:
        delivery = db.get(AlertDelivery, delivery_id)
        if delivery is None:
            logger.warning("Alert delivery disappeared before result persistence delivery_id=%s", delivery_id)
            return
        delivery.status = outcome.status
        delivery.provider_message_id = outcome.provider_message_id
        if outcome.provider_data:
            delivery.provider_data = _merge_provider_data(
                delivery.provider_data,
                outcome.provider_data,
            )
        if outcome.expired_subscription_ids:
            db.execute(
                delete(PushSubscription).where(
                    PushSubscription.id.in_(outcome.expired_subscription_ids)
                )
            )
        db.commit()


def drain_pending_deliveries(stop_event: threading.Event | None = None) -> DrainResult:
    recovered = _recover_interrupted_deliveries()
    sent = 0
    failed = recovered
    while stop_event is None or not stop_event.is_set():
        claimed = _claim_next_delivery()
        if claimed is None:
            break
        if claimed.payload is None:
            failed += 1
            continue

        try:
            if isinstance(claimed.payload, EmailAlertPayload):
                outcome = send_email_alert(claimed.payload)
            else:
                outcome = send_push_alert(claimed.payload)
        except Exception:
            logger.exception("Unexpected alert delivery failure delivery_id=%s", claimed.id)
            outcome = DeliveryOutcome(
                status="failed",
                provider_data={"error": "unexpected_delivery_error"},
            )

        _save_outcome(claimed.id, outcome)
        if outcome.status == "sent":
            sent += 1
        else:
            failed += 1

    result = DrainResult(recovered=recovered, sent=sent, failed=failed)
    if recovered or sent or failed:
        logger.info(
            "Alert delivery drain completed recovered=%s sent=%s failed=%s",
            recovered,
            sent,
            failed,
        )
    return result


def run_delivery_loop(stop_event: threading.Event, wake_event: threading.Event) -> None:
    logger.info("Alert delivery loop started")
    while not stop_event.is_set():
        try:
            with database_source("worker:alert_delivery"):
                drain_pending_deliveries(stop_event)
        except Exception:
            logger.exception("Unexpected alert delivery drain failure")
        if stop_event.is_set():
            break
        wake_event.wait()
        wake_event.clear()
    logger.info("Alert delivery loop stopped")
