from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Game, IngestRun
from worker.ingest import run_ingest_cycle
from worker.providers.base import ProviderGame


class SuccessProvider:
    def fetch_schedule(self):
        return [
            ProviderGame(
                external_game_id="game-1",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
            )
        ]

    def fetch_game_updates(self, external_game_ids):
        return []


class FailingProvider:
    def fetch_schedule(self):
        raise RuntimeError("boom")

    def fetch_game_updates(self, external_game_ids):
        return []


def test_ingest_run_success(db_session):
    result = run_ingest_cycle(SuccessProvider())
    assert result["status"] == "success"
    assert result["games_checked"] == 1
    assert result["games_updated"] == 1

    runs = db_session.scalars(select(IngestRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "success"

    games = db_session.scalars(select(Game)).all()
    assert len(games) == 1


def test_ingest_run_failure(db_session):
    result = run_ingest_cycle(FailingProvider())
    assert result["status"] == "failed"

    runs = db_session.scalars(select(IngestRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "failed"
