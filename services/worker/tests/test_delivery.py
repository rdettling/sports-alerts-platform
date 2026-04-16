from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import ApiCallEvent, Game, SentAlert, Team, User
from worker import delivery
from worker.delivery import process_pending_alerts


def _seed_pending_alert(db_session) -> SentAlert:
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
        delivery_status="pending",
        dedupe_key=f"{user.id}:{game.id}:game_start",
        metadata_json={"status": "in_progress"},
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


def test_email_delivery_success_marks_sent(db_session, monkeypatch):
    alert = _seed_pending_alert(db_session)

    def fake_post(url, json, headers, timeout):
        class Response:
            is_success = True
            status_code = 200
            text = '{"id":"email_123"}'

            @staticmethod
            def json():
                return {"id": "email_123"}

        assert "api.resend.com" in url
        assert json["to"] == ["delivery@example.com"]
        assert json["subject"].startswith("[Sports Alerts] Tip-off:")
        assert "html" in json
        assert "Sports Alerts" in json["html"]
        assert "text" in json
        assert "Bearer test-key" in headers["Authorization"]
        assert timeout == 15.0
        return Response()

    monkeypatch.setattr(delivery.settings, "delivery_mode", "email")
    monkeypatch.setattr(delivery.settings, "resend_api_key", "test-key")
    monkeypatch.setattr(delivery.httpx, "post", fake_post)

    sent_count, failed_count = process_pending_alerts(db_session)
    assert sent_count == 1
    assert failed_count == 0

    updated = db_session.get(SentAlert, alert.id)
    assert updated is not None
    assert updated.delivery_status == "sent"
    assert updated.provider_message_id == "email_123"
    assert updated.metadata_json == {"status": "in_progress"}
    resend_events = db_session.scalars(select(ApiCallEvent).where(ApiCallEvent.provider == "resend")).all()
    assert len(resend_events) == 1
    assert resend_events[0].attempt_status == "success"


def test_email_delivery_failure_marks_failed_and_keeps_metadata(db_session, monkeypatch):
    alert = _seed_pending_alert(db_session)

    def fake_post(url, json, headers, timeout):
        class Response:
            is_success = False
            status_code = 401
            text = "unauthorized"

            @staticmethod
            def json():
                return {"message": "unauthorized"}

        return Response()

    monkeypatch.setattr(delivery.settings, "delivery_mode", "email")
    monkeypatch.setattr(delivery.settings, "resend_api_key", "bad-key")
    monkeypatch.setattr(delivery.httpx, "post", fake_post)

    sent_count, failed_count = process_pending_alerts(db_session)
    assert sent_count == 0
    assert failed_count == 1

    updated = db_session.get(SentAlert, alert.id)
    assert updated is not None
    assert updated.delivery_status == "failed"
    assert updated.metadata_json is not None
    assert updated.metadata_json["status"] == "in_progress"
    assert updated.metadata_json["error"] == "resend_request_failed"
    assert updated.metadata_json["status_code"] == 401
    resend_events = db_session.scalars(select(ApiCallEvent).where(ApiCallEvent.provider == "resend")).all()
    assert len(resend_events) == 1
    assert resend_events[0].attempt_status == "error"
