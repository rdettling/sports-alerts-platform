import threading
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import main as backend
from app.db import backup
from app.services import worker_schedule
from app.worker import runtime, scheduler, updates
from app.worker.scoreboard import ScoreboardGame


def test_combined_backend_ingests_and_stops_cleanly(tmp_path, monkeypatch):
    changed = threading.Event()
    publish = updates.notify_games_changed

    def notify(competition):
        result = publish(competition)
        if competition == "NCAAB":
            changed.set()
        return result

    def fetch_games(self, competition, dates):
        if competition != "NCAAB":
            return []
        return [
            ScoreboardGame(
                external_game_id="combined-runtime",
                home_external_team_id="150",
                away_external_team_id="153",
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
                status="scheduled",
            )
        ]

    monkeypatch.setattr(backend, "running_worker", runtime.running_worker)
    monkeypatch.setattr(scheduler.EspnScoreboardClient, "fetch_games", fetch_games)
    monkeypatch.setattr(
        scheduler,
        "create_daily_backup",
        lambda: backup.backup_database(tmp_path / "startup.db"),
    )
    monkeypatch.setattr(updates, "notify_games_changed", notify)
    with TestClient(backend.app) as client:
        assert changed.wait(10), "Scheduler did not ingest the college basketball game"
        assert client.get("/healthz").status_code == 200
        games = client.get("/games?competition=NCAAB").json()
        assert [game["external_game_id"] for game in games] == ["combined-runtime"]
        assert games[0]["home_team"]["name"] == "Duke Blue Devils"
        assert worker_schedule.snapshot is not None
        assert len(worker_schedule.snapshot.jobs) == 33
        assert (tmp_path / "startup.db").exists()
        assert (
            client.post(
                "/internal/updates/games", json={"competition": "NBA"}
            ).status_code
            == 404
        )
        threads = backend.app.state.worker_threads
    assert not any(thread.is_alive() for thread in threads)


def test_health_reports_stopped_background_thread(client, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        backend.app.state, "worker_threads", [SimpleNamespace(is_alive=lambda: False)]
    )
    assert client.get("/healthz").status_code == 503


def test_second_backend_is_rejected_before_database_writes(client, monkeypatch):
    import pytest

    def unexpected(_db):
        pytest.fail("A second backend must not seed the active database")

    monkeypatch.setattr(backend, "ensure_seeded_teams", unexpected)
    with pytest.raises(RuntimeError, match="Another backend"):
        with TestClient(backend.app):
            pytest.fail("A second backend must not start")
    assert client.get("/healthz").status_code == 200
