import httpx

from app.worker import updates


def _configure(monkeypatch):
    monkeypatch.setattr(updates.settings, "live_update_api_url", "https://api.example.com/")
    monkeypatch.setattr(updates.settings, "live_update_secret", "secret")
    monkeypatch.setattr(updates, "_delivery_failing", False)


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
    outcomes = [httpx.ConnectError("offline"), httpx.ConnectError("still offline"), None]

    def post(url, **_kwargs):
        outcome = outcomes.pop(0)
        if outcome:
            raise outcome
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(updates.httpx, "post", post)

    with caplog.at_level("INFO", logger="app.worker.updates"):
        assert updates.notify_games_changed("NBA") is False
        assert updates.notify_games_changed("NBA") is False
        assert updates.notify_games_changed("NBA") is True

    assert caplog.text.count("Live update delivery failed") == 1
    assert caplog.text.count("Live update delivery recovered") == 1
