from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import ApiCallRollupHourly, Game, SentAlert, Team, User
from app.services import alert_delivery
from app.services.alert_delivery import deliver_alert_now
from app.services.email_branding import APP_BRAND_NAME


def _seed_alert(db_session) -> SentAlert:
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

    alert = SentAlert(
        user_id=user.id,
        game_id=game.id,
        alert_type="game_start",
        delivery_channel="email",
        delivery_status="sent",
        dedupe_key=f"{user.id}:{game.id}:game_start",
        metadata_json={"status": "in_progress"},
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


def test_email_delivery_success_marks_sent(db_session, monkeypatch):
    alert = _seed_alert(db_session)

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

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "email")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(alert_delivery, "urlopen", fake_urlopen)

    user = db_session.get(User, alert.user_id)
    game = db_session.get(Game, alert.game_id)
    assert user is not None
    assert game is not None
    home = db_session.get(Team, game.home_team_id)
    away = db_session.get(Team, game.away_team_id)
    status = deliver_alert_now(
        db_session,
        alert=alert,
        user=user,
        game=game,
        home=home,
        away=away,
        service="worker",
    )
    assert status == "sent"

    updated = db_session.get(SentAlert, alert.id)
    assert updated is not None
    assert updated.delivery_status == "sent"
    assert updated.provider_message_id == "email_123"
    assert updated.metadata_json == {"status": "in_progress"}
    resend_rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend")).all()
    assert len(resend_rollups) == 1
    assert resend_rollups[0].attempt_status == "success"


def test_email_delivery_failure_marks_failed_and_keeps_metadata(db_session, monkeypatch):
    alert = _seed_alert(db_session)

    class ErrorResponse:
        def read(self):
            return b"unauthorized"

        def close(self):
            return None

    def fake_urlopen(request, timeout):
        raise alert_delivery.HTTPError(request.full_url, 401, "unauthorized", hdrs=None, fp=ErrorResponse())

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "email")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "bad-key")
    monkeypatch.setattr(alert_delivery, "urlopen", fake_urlopen)

    user = db_session.get(User, alert.user_id)
    game = db_session.get(Game, alert.game_id)
    assert user is not None
    assert game is not None
    home = db_session.get(Team, game.home_team_id)
    away = db_session.get(Team, game.away_team_id)
    status = deliver_alert_now(
        db_session,
        alert=alert,
        user=user,
        game=game,
        home=home,
        away=away,
        service="worker",
    )
    assert status == "failed"

    updated = db_session.get(SentAlert, alert.id)
    assert updated is not None
    assert updated.delivery_status == "failed"
    assert updated.metadata_json is not None
    assert updated.metadata_json["status"] == "in_progress"
    assert updated.metadata_json["error"] == "resend_request_failed"
    assert updated.metadata_json["status_code"] == 401
    resend_rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend")).all()
    assert len(resend_rollups) == 1
    assert resend_rollups[0].attempt_status == "error"


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

    alert = SentAlert(
        user_id=user.id,
        game_id=game.id,
        alert_type="score_changed",
        delivery_channel="email",
        delivery_status="sent",
        dedupe_key=f"{user.id}:{game.id}:score_changed:2-2",
        metadata_json={
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

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "email")
    monkeypatch.setattr(alert_delivery.delivery_settings, "resend_api_key", "test-key")
    monkeypatch.setattr(alert_delivery, "urlopen", fake_urlopen)

    persisted = db_session.scalar(select(SentAlert).where(SentAlert.id == alert.id))
    assert persisted is not None
    status = deliver_alert_now(
        db_session,
        alert=persisted,
        user=user,
        game=game,
        home=db_session.get(Team, game.home_team_id),
        away=db_session.get(Team, game.away_team_id),
        service="worker",
    )
    assert status == "sent"
