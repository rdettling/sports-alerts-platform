import httpx
import pytest

from app.worker import updates


def _configure(monkeypatch):
    monkeypatch.setattr(updates.settings, "live_update_api_url", "https://api.example.com/")
    monkeypatch.setattr(updates.settings, "live_update_secret", "secret")
    monkeypatch.setattr(updates, "_delivery_failures", set())


def test_notification_is_disabled_without_complete_configuration(monkeypatch):
    monkeypatch.setattr(updates.settings, "live_update_api_url", "")
    monkeypatch.setattr(updates.settings, "live_update_secret", "")
    monkeypatch.setattr(
        updates.httpx,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not request")),
    )

    assert updates.notify_games_changed("NBA") is False


def test_notification_posts_authenticated_competition_without_retries(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(updates.httpx, "post", post)

    assert updates.notify_games_changed("NBA") is True
    assert calls == [
        (
            "https://api.example.com/internal/updates/games",
            {
                "headers": {"X-Live-Update-Secret": "secret"},
                "json": {"competition": "NBA"},
                "timeout": 2.0,
            },
        )
    ]


def test_notification_suppresses_repeated_failures_and_logs_recovery(monkeypatch, caplog):
    _configure(monkeypatch)
    outcomes = [httpx.ConnectError("offline")] * 4 + [None]

    def post(url, **_kwargs):
        outcome = outcomes.pop(0)
        if outcome:
            raise outcome
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(updates.httpx, "post", post)
    monkeypatch.setattr(updates, "sleep", lambda _: None)

    with caplog.at_level("INFO", logger="app.worker.updates"):
        assert updates.notify_games_changed("NBA") is False
        assert updates.notify_games_changed("NBA") is False
        assert updates.notify_games_changed("NBA") is True

    assert caplog.text.count("Live update delivery failed") == 1
    assert caplog.text.count("Live update delivery recovered") == 1


@pytest.mark.parametrize("failure", [
    httpx.ReadTimeout("timed out"),
    httpx.ConnectError("offline"),
    httpx.RemoteProtocolError("disconnected"),
    500, 502, 503, 504,
])
def test_transient_failure_retries_once_then_recovers(monkeypatch, failure):
    _configure(monkeypatch)
    calls, delays = [], []

    def post(url, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            if isinstance(failure, Exception):
                raise failure
            return httpx.Response(failure, request=httpx.Request("POST", url))
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(updates.httpx, "post", post)
    monkeypatch.setattr(updates, "sleep", delays.append)
    assert updates.notify_games_changed("NBA") is True
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert calls[0]["timeout"] == 2.0
    assert delays == [0.25]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_publish_failure_has_bounded_attempts(monkeypatch, status):
    _configure(monkeypatch)
    calls, delays = [], []

    def post(url, **kwargs):
        calls.append(url)
        return httpx.Response(status, request=httpx.Request("POST", url))

    monkeypatch.setattr(updates.httpx, "post", post)
    monkeypatch.setattr(updates, "sleep", delays.append)
    assert updates.notify_games_changed("NBA") is False
    assert len(calls) == (2 if status >= 500 else 1)
    assert delays == ([0.25] if status >= 500 else [])


def test_schedule_transport_serializes_times_and_keeps_failure_logs_independent(monkeypatch, caplog):
    from app.schemas.schedule import ScheduleSnapshot
    _configure(monkeypatch)
    snapshot = ScheduleSnapshot(reported_at="2026-09-04T16:00:00Z", next_catalog_at="2026-09-05T04:00:00Z", jobs=[])
    calls, delays = [], []
    failing = True

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(503 if failing and url.endswith("schedule") else 204,
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(updates.httpx, "post", post)
    monkeypatch.setattr(updates, "sleep", delays.append)
    with caplog.at_level("INFO", logger="app.worker.updates"):
        assert updates.notify_schedule(snapshot) is False
        assert updates.notify_games_changed("NBA") is True
        assert updates.notify_schedule(snapshot) is False
        failing = False
        assert updates.notify_schedule(snapshot) is True
    assert delays == [0.25, 0.25]
    assert calls[0] == ("https://api.example.com/internal/updates/schedule", {
        "headers": {"X-Live-Update-Secret": "secret"},
        "json": {"reported_at": "2026-09-04T16:00:00Z", "next_catalog_at": "2026-09-05T04:00:00Z", "jobs": []}, "timeout": 2.0,
    })
    assert caplog.text.count("Schedule report delivery failed") == 1
    assert caplog.text.count("Schedule report delivery recovered") == 1
