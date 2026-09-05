from datetime import datetime, timezone
from threading import Event

import pytest
from sqlalchemy import event, select

from app.db.models import Alert, AlertDelivery, Game, PushSubscription, Team, User
from app.db.session import engine
from app.services import alert_delivery, resend
from app.services.alert_delivery import (
    DeliveryOutcome,
    build_email_payload,
    build_push_payload,
    send_email_alert,
    send_push_alert,
)
from app.services.email_branding import APP_BRAND_NAME
from app.worker import delivery as worker_delivery


def _seed_alert(db_session, *, channel: str = "email") -> tuple[Alert, AlertDelivery]:
    user = User(email="delivery@example.com")
    db_session.add(user)
    db_session.flush()
    teams = db_session.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
    game = Game(
        external_game_id=f"delivery-game-{channel}-{user.id}",
        competition="NBA",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=101,
        away_score=99,
    )
    db_session.add(game)
    db_session.flush()
    alert = Alert(
        user_id=user.id,
        game_id=game.id,
        alert_type="game_start",
        event_key=f"{user.id}:{game.id}:game_start",
        event_data={
            "status": "in_progress",
            "period": 1,
            "clock": "11:42",
            "home_score": 101,
            "away_score": 99,
        },
    )
    db_session.add(alert)
    db_session.flush()
    delivery = AlertDelivery(alert_id=alert.id, channel=channel, status="pending")
    db_session.add(delivery)
    db_session.commit()
    return alert, delivery


def _email_payload(db_session, alert: Alert, delivery: AlertDelivery):
    user = db_session.get(User, alert.user_id)
    game = db_session.get(Game, alert.game_id)
    assert user is not None and game is not None
    return build_email_payload(
        alert=alert,
        delivery_id=delivery.id,
        user=user,
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        service="worker",
    )


def _push_payload(db_session, alert: Alert):
    game = db_session.get(Game, alert.game_id)
    assert game is not None
    subscriptions = db_session.scalars(
        select(PushSubscription)
        .where(PushSubscription.user_id == alert.user_id)
        .order_by(PushSubscription.id.asc())
    ).all()
    return build_push_payload(
        alert=alert,
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        subscriptions=list(subscriptions),
        service="worker",
    )


def test_email_sender_returns_success_without_mutating_database(db_session, monkeypatch):
    alert, delivery = _seed_alert(db_session)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"id":"email_123"}'

    def fake_urlopen(request, timeout):
        body = request.data.decode("utf-8")
        assert "delivery@example.com" in body
        assert "Tip-off" in body
        assert APP_BRAND_NAME in body
        assert timeout == 15.0
        return Response()

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(resend, "urlopen", fake_urlopen)

    outcome = send_email_alert(_email_payload(db_session, alert, delivery))

    assert outcome == DeliveryOutcome(status="sent", provider_message_id="email_123")
    db_session.refresh(delivery)
    assert delivery.status == "pending"
    assert delivery.attempted_at is None


def test_email_sender_returns_provider_failure_metadata(db_session, monkeypatch, caplog):
    alert, delivery = _seed_alert(db_session)

    class ErrorResponse:
        def read(self):
            return b"unauthorized"

        def close(self):
            return None

    def fake_urlopen(request, timeout):
        raise resend.HTTPError(
            request.full_url,
            401,
            "unauthorized",
            hdrs=None,
            fp=ErrorResponse(),
        )

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "bad-key")
    monkeypatch.setattr(resend, "urlopen", fake_urlopen)

    outcome = send_email_alert(_email_payload(db_session, alert, delivery))

    assert outcome.status == "failed"
    assert outcome.provider_data["error"] == "resend_request_failed"
    assert outcome.provider_data["status_code"] == 401
    assert "Alert email delivery failed service=worker" in caplog.text


def test_email_sender_log_mode_skips_provider(db_session, monkeypatch):
    alert, delivery = _seed_alert(db_session)
    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "log")
    monkeypatch.setattr(
        resend,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected request")),
    )

    outcome = send_email_alert(_email_payload(db_session, alert, delivery))

    assert outcome == DeliveryOutcome(
        status="sent",
        provider_message_id=f"log-{delivery.id}",
    )


def test_resend_network_failure_returns_metadata(monkeypatch):
    monkeypatch.setattr(resend.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(
        resend,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(resend.URLError("network unavailable")),
    )

    result = resend.send_resend_email(
        to_email="delivery@example.com",
        subject="Test",
        text_body="Test",
        html_body="<p>Test</p>",
    )

    assert result.sent is False
    assert result.metadata == {
        "error": "resend_http_error",
        "detail": "network unavailable",
    }


def test_push_sender_aggregates_devices_without_mutating_subscriptions(db_session, monkeypatch):
    alert, _ = _seed_alert(db_session)
    db_session.add_all(
        [
            PushSubscription(
                user_id=alert.user_id,
                endpoint="https://push.example/gone",
                p256dh="p" * 43,
                auth="a" * 22,
            ),
            PushSubscription(
                user_id=alert.user_id,
                endpoint="https://push.example/active",
                p256dh="p" * 43,
                auth="b" * 22,
            ),
        ]
    )
    db_session.commit()

    class GoneResponse:
        status_code = 410

    def fake_webpush(**kwargs):
        if kwargs["subscription_info"]["endpoint"].endswith("/gone"):
            raise alert_delivery.WebPushException("gone", response=GoneResponse())
        assert kwargs["timeout"] == 10
        assert kwargs["ttl"] == 300

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_private_key", "private")
    monkeypatch.setattr(alert_delivery, "webpush", fake_webpush)

    outcome = send_push_alert(_push_payload(db_session, alert))

    assert outcome.status == "sent"
    assert outcome.provider_data == {"attempted": 2, "sent": 1, "expired": 1}
    assert len(outcome.expired_subscription_ids) == 1
    assert len(db_session.scalars(select(PushSubscription)).all()) == 2


def test_dispatcher_sends_outside_database_checkout(db_session, monkeypatch):
    _, delivery = _seed_alert(db_session)
    active_connections = 0

    def checkout(*_args):
        nonlocal active_connections
        active_connections += 1

    def checkin(*_args):
        nonlocal active_connections
        active_connections -= 1

    event.listen(engine, "checkout", checkout)
    event.listen(engine, "checkin", checkin)

    def send(payload):
        assert active_connections == 0
        return DeliveryOutcome(status="sent", provider_message_id="provider-1")

    monkeypatch.setattr(worker_delivery, "send_email_alert", send)
    try:
        result = worker_delivery.drain_pending_deliveries()
    finally:
        event.remove(engine, "checkout", checkout)
        event.remove(engine, "checkin", checkin)

    db_session.expire_all()
    persisted = db_session.get(AlertDelivery, delivery.id)
    assert result.sent == 1
    assert persisted is not None
    assert persisted.status == "sent"
    assert persisted.attempted_at is not None
    assert persisted.provider_message_id == "provider-1"


def test_dispatcher_recovers_unattempted_but_never_retries_interrupted(
    db_session,
    monkeypatch,
):
    _, first = _seed_alert(db_session)
    first.attempted_at = datetime.now(timezone.utc)
    db_session.commit()
    calls: list[int] = []
    monkeypatch.setattr(
        worker_delivery,
        "send_email_alert",
        lambda payload: calls.append(payload.alert_id) or DeliveryOutcome(status="sent"),
    )

    result = worker_delivery.drain_pending_deliveries()

    db_session.expire_all()
    interrupted = db_session.get(AlertDelivery, first.id)
    assert result.recovered == 1
    assert result.failed == 1
    assert calls == []
    assert interrupted is not None
    assert interrupted.status == "failed"
    assert interrupted.provider_data == {"error": "interrupted_during_delivery"}


def test_dispatcher_processes_pending_deliveries_in_id_order(db_session, monkeypatch):
    first_alert, first = _seed_alert(db_session)
    second_user = User(email="second@example.com")
    db_session.add(second_user)
    db_session.flush()
    second_alert = Alert(
        user_id=second_user.id,
        game_id=first_alert.game_id,
        alert_type="game_start",
        event_key=f"{second_user.id}:{first_alert.game_id}:game_start",
        event_data=first_alert.event_data,
    )
    db_session.add(second_alert)
    db_session.flush()
    second = AlertDelivery(alert_id=second_alert.id, channel="email", status="pending")
    db_session.add(second)
    db_session.commit()
    calls: list[int] = []
    monkeypatch.setattr(
        worker_delivery,
        "send_email_alert",
        lambda payload: calls.append(payload.delivery_id) or DeliveryOutcome(status="sent"),
    )

    result = worker_delivery.drain_pending_deliveries()

    assert result.sent == 2
    assert calls == [first.id, second.id]


def test_dispatcher_persists_expired_push_cleanup_after_send(db_session, monkeypatch):
    alert, delivery = _seed_alert(db_session, channel="push")
    subscription = PushSubscription(
        user_id=alert.user_id,
        endpoint="https://push.example/gone",
        p256dh="p" * 43,
        auth="a" * 22,
    )
    db_session.add(subscription)
    db_session.commit()
    subscription_id = subscription.id
    active_connections = 0

    def checkout(*_args):
        nonlocal active_connections
        active_connections += 1

    def checkin(*_args):
        nonlocal active_connections
        active_connections -= 1

    def send(_payload):
        assert active_connections == 0
        return DeliveryOutcome(
            status="failed",
            provider_data={"error": "all_subscriptions_expired"},
            expired_subscription_ids=(subscription_id,),
        )

    event.listen(engine, "checkout", checkout)
    event.listen(engine, "checkin", checkin)
    monkeypatch.setattr(worker_delivery, "send_push_alert", send)

    try:
        result = worker_delivery.drain_pending_deliveries()
    finally:
        event.remove(engine, "checkout", checkout)
        event.remove(engine, "checkin", checkin)

    db_session.expire_all()
    assert result.failed == 1
    assert db_session.get(PushSubscription, subscription_id) is None
    assert db_session.get(AlertDelivery, delivery.id).status == "failed"


def test_result_persistence_failure_leaves_attempt_mark_for_safe_recovery(
    db_session,
    monkeypatch,
):
    _, delivery = _seed_alert(db_session)
    monkeypatch.setattr(
        worker_delivery,
        "send_email_alert",
        lambda payload: DeliveryOutcome(status="sent"),
    )
    monkeypatch.setattr(
        worker_delivery,
        "_save_outcome",
        lambda *args: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        worker_delivery.drain_pending_deliveries()

    db_session.expire_all()
    attempted = db_session.get(AlertDelivery, delivery.id)
    assert attempted is not None
    assert attempted.status == "pending"
    assert attempted.attempted_at is not None


def test_delivery_loop_drains_once_then_waits_without_polling(monkeypatch):
    stop_event = Event()
    drains: list[bool] = []

    class WakeEvent:
        def wait(self):
            stop_event.set()

        def clear(self):
            return None

    monkeypatch.setattr(
        worker_delivery,
        "drain_pending_deliveries",
        lambda stop: drains.append(stop is stop_event) or worker_delivery.DrainResult(),
    )

    worker_delivery.run_delivery_loop(stop_event, WakeEvent())

    assert drains == [True]
