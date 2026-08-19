from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Alert, AlertDelivery, ApiCallRollupHourly, Game, PushSubscription, Team, User
from app.services import alert_delivery, resend
from app.services.alert_delivery import deliver_email_alert_now, deliver_push_alert_now
from app.services.email_branding import APP_BRAND_NAME


def _seed_alert(db_session) -> tuple[Alert, AlertDelivery]:
    user = User(email="delivery@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
    game = Game(
        external_game_id="delivery-game",
        league="NBA",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=101,
        away_score=99,
    )
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)

    alert = Alert(
        user_id=user.id,
        game_id=game.id,
        alert_type="game_start",
        event_key=f"{user.id}:{game.id}:game_start",
        event_data={"status": "in_progress"},
    )
    db_session.add(alert)
    db_session.flush()
    delivery = AlertDelivery(alert_id=alert.id, channel="email", status="pending")
    db_session.add(delivery)
    db_session.commit()
    return alert, delivery


def test_email_delivery_success_marks_sent(db_session, monkeypatch):
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
        assert "api.resend.com" in request.full_url
        body = request.data.decode("utf-8")
        assert "delivery@example.com" in body
        assert "Tip-off" in body
        assert APP_BRAND_NAME in body
        assert request.headers["Authorization"] == "Bearer test-key"
        assert timeout == 15.0
        return Response()

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(resend, "urlopen", fake_urlopen)

    user = db_session.get(User, alert.user_id)
    game = db_session.get(Game, alert.game_id)
    assert user is not None
    assert game is not None
    home = db_session.get(Team, game.home_team_id)
    away = db_session.get(Team, game.away_team_id)
    status = deliver_email_alert_now(
        db_session,
        alert=alert,
        delivery=delivery,
        user=user,
        game=game,
        home=home,
        away=away,
        service="worker",
    )
    assert status == "sent"

    updated = db_session.get(AlertDelivery, delivery.id)
    assert updated is not None
    assert updated.status == "sent"
    assert updated.provider_message_id == "email_123"
    assert updated.provider_data is None
    assert alert.event_data == {"status": "in_progress"}
    resend_rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend")).all()
    assert len(resend_rollups) == 1
    assert resend_rollups[0].attempt_status == "success"


def test_email_delivery_failure_marks_failed_and_keeps_metadata(db_session, monkeypatch):
    alert, delivery = _seed_alert(db_session)

    class ErrorResponse:
        def read(self):
            return b"unauthorized"

        def close(self):
            return None

    def fake_urlopen(request, timeout):
        raise resend.HTTPError(request.full_url, 401, "unauthorized", hdrs=None, fp=ErrorResponse())

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "bad-key")
    monkeypatch.setattr(resend, "urlopen", fake_urlopen)

    user = db_session.get(User, alert.user_id)
    game = db_session.get(Game, alert.game_id)
    assert user is not None
    assert game is not None
    home = db_session.get(Team, game.home_team_id)
    away = db_session.get(Team, game.away_team_id)
    status = deliver_email_alert_now(
        db_session,
        alert=alert,
        delivery=delivery,
        user=user,
        game=game,
        home=home,
        away=away,
        service="worker",
    )
    assert status == "failed"

    updated = db_session.get(AlertDelivery, delivery.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.provider_data is not None
    assert alert.event_data == {"status": "in_progress"}
    assert updated.provider_data["error"] == "resend_request_failed"
    assert updated.provider_data["status_code"] == 401
    resend_rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend")).all()
    assert len(resend_rollups) == 1
    assert resend_rollups[0].attempt_status == "error"


def test_email_delivery_log_mode_marks_delivery_sent_without_provider_call(db_session, monkeypatch):
    alert, delivery = _seed_alert(db_session)

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("log mode must not call Resend")

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "log")
    monkeypatch.setattr(resend, "urlopen", fail_urlopen)

    game = db_session.get(Game, alert.game_id)
    assert game is not None
    status = deliver_email_alert_now(
        db_session,
        alert=alert,
        delivery=delivery,
        user=db_session.get(User, alert.user_id),
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        service="worker",
    )

    assert status == "sent"
    assert delivery.provider_message_id == f"log-{delivery.id}"
    assert delivery.attempted_at is not None
    assert alert.event_data == {"status": "in_progress"}


def test_email_delivery_without_resend_key_marks_only_delivery_failed(db_session, monkeypatch):
    alert, delivery = _seed_alert(db_session)
    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "")

    game = db_session.get(Game, alert.game_id)
    assert game is not None
    status = deliver_email_alert_now(
        db_session,
        alert=alert,
        delivery=delivery,
        user=db_session.get(User, alert.user_id),
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        service="worker",
    )

    assert status == "failed"
    assert delivery.provider_data == {"error": "missing_resend_api_key"}
    assert alert.event_data == {"status": "in_progress"}


def test_resend_success_without_message_id_returns_warning(db_session, monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b"{}"

    monkeypatch.setattr(resend.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(resend, "urlopen", lambda request, timeout: Response())

    result = resend.send_resend_email(
        db_session,
        service="worker",
        to_email="delivery@example.com",
        subject="Test",
        text_body="Test",
        html_body="<p>Test</p>",
    )

    assert result.sent is True
    assert result.provider_message_id is None
    assert result.metadata == {"provider_warning": "missing_message_id"}


def test_resend_network_failure_returns_metadata_and_records_telemetry(db_session, monkeypatch):
    def fail_urlopen(request, timeout):
        raise resend.URLError("network unavailable")

    monkeypatch.setattr(resend.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(resend, "urlopen", fail_urlopen)

    result = resend.send_resend_email(
        db_session,
        service="worker",
        to_email="delivery@example.com",
        subject="Test",
        text_body="Test",
        html_body="<p>Test</p>",
    )

    assert result.sent is False
    assert result.metadata == {"error": "resend_http_error", "detail": "network unavailable"}
    db_session.flush()
    rollup = db_session.scalar(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend"))
    assert rollup is not None
    assert rollup.attempt_status == "error"


def test_score_changed_delivery_uses_metadata_scores_for_subject(db_session, monkeypatch):
    user = User(email="score-changed@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()).limit(2)).all()
    game = Game(
        external_game_id="delivery-world-cup-game",
        league="WORLD_CUP",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=2,
        away_score=2,
        period=2,
        clock="70'",
    )
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)

    alert = Alert(
        user_id=user.id,
        game_id=game.id,
        alert_type="score_changed",
        event_key=f"{user.id}:{game.id}:score_changed:2-2",
        event_data={
            "status": "in_progress",
            "period": 2,
            "clock": "68'",
            "previous_home_score": 1,
            "previous_away_score": 1,
            "new_home_score": 2,
            "new_away_score": 2,
            "scoring_side": None,
            "is_inferred_goal": False,
        },
    )
    db_session.add(alert)
    db_session.flush()
    delivery = AlertDelivery(alert_id=alert.id, channel="email", status="pending")
    db_session.add(delivery)
    db_session.commit()

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"id":"email_456"}'

    def fake_urlopen(request, timeout):
        body = request.data.decode("utf-8")
        assert "Score update \\u00b7 USA 2\\u20132 MEX" in body
        assert "68'" in body
        return Response()

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(resend, "urlopen", fake_urlopen)

    persisted = db_session.scalar(select(Alert).where(Alert.id == alert.id))
    assert persisted is not None
    status = deliver_email_alert_now(
        db_session,
        alert=persisted,
        delivery=delivery,
        user=user,
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        service="worker",
    )
    assert status == "sent"


def _push_delivery(db_session, alert: Alert) -> AlertDelivery:
    delivery = AlertDelivery(alert_id=alert.id, channel="push", status="pending")
    db_session.add(delivery)
    db_session.commit()
    return delivery


def _deliver_push(db_session, alert: Alert, delivery: AlertDelivery) -> str:
    game = db_session.get(Game, alert.game_id)
    assert game is not None
    return deliver_push_alert_now(
        db_session,
        alert=alert,
        delivery=delivery,
        user=db_session.get(User, alert.user_id),
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        service="worker",
    )


def test_push_delivery_sends_every_device_and_aggregates_success(db_session, monkeypatch):
    alert, _ = _seed_alert(db_session)
    delivery = _push_delivery(db_session, alert)
    db_session.add_all(
        [
            PushSubscription(
                user_id=alert.user_id,
                endpoint="https://push.example/one",
                p256dh="p" * 43,
                auth="a" * 22,
            ),
            PushSubscription(
                user_id=alert.user_id,
                endpoint="https://push.example/two",
                p256dh="p" * 43,
                auth="b" * 22,
            ),
        ]
    )
    db_session.commit()
    sent_endpoints: list[str] = []

    def fake_webpush(**kwargs):
        sent_endpoints.append(kwargs["subscription_info"]["endpoint"])
        assert kwargs["ttl"] == 300
        assert kwargs["timeout"] == 10
        assert kwargs["vapid_claims"] == {"sub": "mailto:alerts@example.com"}

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_subject", "mailto:alerts@example.com")
    monkeypatch.setattr(alert_delivery, "webpush", fake_webpush)

    assert _deliver_push(db_session, alert, delivery) == "sent"
    assert sent_endpoints == ["https://push.example/one", "https://push.example/two"]
    assert delivery.provider_data == {"attempted": 2, "sent": 2, "expired": 0}


def test_push_delivery_keeps_success_and_deletes_expired_device(db_session, monkeypatch):
    alert, _ = _seed_alert(db_session)
    delivery = _push_delivery(db_session, alert)
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

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(alert_delivery, "webpush", fake_webpush)

    assert _deliver_push(db_session, alert, delivery) == "sent"
    assert delivery.provider_data == {"attempted": 2, "sent": 1, "expired": 1}
    remaining = db_session.scalars(select(PushSubscription)).all()
    assert [row.endpoint for row in remaining] == ["https://push.example/active"]


def test_push_delivery_total_provider_failure_retains_subscription(db_session, monkeypatch):
    alert, _ = _seed_alert(db_session)
    delivery = _push_delivery(db_session, alert)
    db_session.add(
        PushSubscription(
            user_id=alert.user_id,
            endpoint="https://push.example/retry-later",
            p256dh="p" * 43,
            auth="a" * 22,
        )
    )
    db_session.commit()

    class FailureResponse:
        status_code = 503

    def fake_webpush(**kwargs):
        raise alert_delivery.WebPushException("unavailable", response=FailureResponse())

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(alert_delivery, "webpush", fake_webpush)

    assert _deliver_push(db_session, alert, delivery) == "failed"
    assert delivery.provider_data == {
        "attempted": 1,
        "sent": 0,
        "expired": 0,
        "errors": ["http_503"],
    }
    assert db_session.scalar(select(PushSubscription)) is not None


def test_push_delivery_without_subscriptions_or_vapid_fails_only_delivery(db_session, monkeypatch):
    alert, _ = _seed_alert(db_session)
    no_subscription = _push_delivery(db_session, alert)
    assert _deliver_push(db_session, alert, no_subscription) == "failed"
    assert no_subscription.provider_data["error"] == "no_active_subscriptions"
    assert alert.event_data == {"status": "in_progress"}

    db_session.add(
        PushSubscription(
            user_id=alert.user_id,
            endpoint="https://push.example/config",
            p256dh="p" * 43,
            auth="a" * 22,
        )
    )
    db_session.delete(no_subscription)
    db_session.flush()
    missing_config = AlertDelivery(alert_id=alert.id, channel="push", status="pending")
    db_session.add(missing_config)
    db_session.commit()
    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_private_key", "")

    assert _deliver_push(db_session, alert, missing_config) == "failed"
    assert missing_config.provider_data == {"error": "missing_vapid_private_key"}
    assert alert.event_data == {"status": "in_progress"}
