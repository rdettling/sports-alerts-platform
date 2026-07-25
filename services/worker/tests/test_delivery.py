from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Alert, AlertDelivery, ApiCallRollupHourly, Game, Team, User
from app.services import alert_delivery
from app.services.alert_delivery import deliver_email_alert_now
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
    monkeypatch.setattr(alert_delivery, "urlopen", fake_urlopen)

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
        raise alert_delivery.HTTPError(request.full_url, 401, "unauthorized", hdrs=None, fp=ErrorResponse())

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "bad-key")
    monkeypatch.setattr(alert_delivery, "urlopen", fake_urlopen)

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
    monkeypatch.setattr(alert_delivery, "urlopen", fail_urlopen)

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
    monkeypatch.setattr(alert_delivery, "urlopen", fake_urlopen)

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
