from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import ApiCallRollupHourly, Game, LeagueSetting, Team
from app.services.leagues import ensure_league_settings
from worker.ingest import run_catalog_sync, run_live_sync

from ingest_support import (
    ContextLabelProvider,
    StaticProvider,
    TelemetryRecordingProvider,
    make_game,
    make_success_provider,
)


def test_ingest_run_success(db_session):
    provider = make_success_provider()
    result = run_catalog_sync(provider)
    assert result["status"] == "success"
    assert result["games_checked"] == 1
    assert result["games_updated"] == 1
    assert result["next_poll_seconds"] >= 30

    games = db_session.scalars(select(Game)).all()
    assert len(games) == 1


def test_ingest_run_failure(db_session):
    result = run_catalog_sync(StaticProvider(error=RuntimeError("boom")))
    assert result["status"] == "failed"
    assert result["next_poll_seconds"] > 0


def test_ingest_attaches_provider_telemetry_context(db_session, monkeypatch):
    provider = TelemetryRecordingProvider()
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)

    result = run_catalog_sync(provider)

    assert result["status"] == "success"
    assert provider.contexts == [True, False]

    rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "espn")).all()
    assert len(rollups) == 1
    assert rollups[0].endpoint_key == "scoreboard"
    assert rollups[0].attempt_status == "success"
    assert rollups[0].call_count == 1


def test_live_sync_returns_next_scheduled_start_when_no_live_games(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-upcoming-1",
            league="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now + timedelta(hours=2),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    result = run_live_sync(StaticProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "waiting_for_start"
    assert result["next_scheduled_start_at"] is not None


def test_live_sync_returns_no_upcoming_when_schedule_empty(db_session):
    result = run_live_sync(StaticProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "no_upcoming"
    assert result["next_scheduled_start_at"] is None


def test_live_sync_keeps_recently_overdue_scheduled_games_hot(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-overdue-1",
            league="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now - timedelta(minutes=20),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    result = run_live_sync(StaticProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "waiting_for_start"
    assert result["next_scheduled_start_at"] is not None


def test_catalog_sync_fails_for_disabled_league(db_session):
    ensure_league_settings(db_session)
    row = db_session.get(LeagueSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    result = run_catalog_sync(StaticProvider(), league="MLB")
    assert result["status"] == "failed"


def test_catalog_sync_fails_when_no_provider_games_map_to_teams(db_session):
    provider = StaticProvider(
        [
            make_game(
                external_game_id="mls-unmapped",
                home_external_team_id="unknown-home",
                away_external_team_id="unknown-away",
                status="scheduled",
            )
        ]
    )

    result = run_catalog_sync(provider, league="MLS")

    assert result["status"] == "failed"
    assert result["error"] == "No MLS games could be mapped to catalog teams"
    assert db_session.scalar(select(Game).where(Game.league == "MLS")) is None


def test_catalog_sync_allows_partial_team_mapping(db_session, monkeypatch):
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="mls-mapped",
                home_external_team_id="187",
                away_external_team_id="18966",
                status="scheduled",
            ),
            make_game(
                external_game_id="mls-all-star",
                home_external_team_id="unknown-home",
                away_external_team_id="unknown-away",
                status="scheduled",
            ),
        ]
    )

    result = run_catalog_sync(provider, league="MLS")

    assert result["status"] == "success"
    assert result["games_checked"] == 2
    assert result["games_updated"] == 1
    games = db_session.scalars(select(Game).where(Game.league == "MLS")).all()
    assert [game.external_game_id for game in games] == ["mls-mapped"]


def test_live_sync_promotes_scheduled_game_to_live(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-angels-like",
            league="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now - timedelta(minutes=15),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    provider = StaticProvider(
        [
            make_game(
                external_game_id="mlb-angels-like",
                home_external_team_id=teams[0].external_team_id,
                away_external_team_id=teams[1].external_team_id,
                scheduled_start_time=now - timedelta(minutes=15),
                status="in_progress",
                home_score=1,
                away_score=0,
                period=2,
                clock="Top 2nd",
                is_final=False,
            )
        ]
    )

    result = run_live_sync(provider, league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "true"
    assert result["mode"] == "live"
    assert result["games_updated"] >= 1

    db_session.expire_all()
    game = db_session.scalar(select(Game).where(Game.external_game_id == "mlb-angels-like", Game.league == "MLB"))
    assert game is not None
    assert game.status == "in_progress"


def test_ingest_persists_and_refreshes_context_label(db_session):
    first = run_catalog_sync(ContextLabelProvider("NBA Finals - Game 5 · NY leads series 3-1"), league="NBA")
    assert first["status"] == "success"

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-context"))
    assert game is not None
    assert game.context_label == "NBA Finals - Game 5 · NY leads series 3-1"

    second = run_catalog_sync(ContextLabelProvider("NBA Finals - Game 5 · Series tied 3-3"), league="NBA")
    assert second["status"] == "success"

    db_session.refresh(game)
    assert game.context_label == "NBA Finals - Game 5 · Series tied 3-3"
