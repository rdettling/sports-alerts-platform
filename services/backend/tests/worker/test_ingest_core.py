from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import Game, CompetitionSetting, Team
from app.services.competitions import competition_teams_query, ensure_competition_settings
from app.worker.ingest import run_catalog_sync, run_live_sync

from ingest_support import (
    ContextLabelProvider,
    StaticProvider,
    make_game,
    make_success_provider,
)


def test_ingest_run_success(db_session):
    provider = make_success_provider()
    result = run_catalog_sync(provider)
    assert result.games_checked == 1
    assert result.games_updated == 1
    assert result.next_live_sync_at is not None
    assert result.next_live_sync_at.tzinfo is not None

    games = db_session.scalars(select(Game)).all()
    assert len(games) == 1


def test_ingest_run_failure(db_session):
    with pytest.raises(RuntimeError, match="boom"):
        run_catalog_sync(StaticProvider(error=RuntimeError("boom")))
    assert db_session.scalar(select(Game)) is None


def test_live_sync_returns_next_scheduled_start_when_no_live_games(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(competition_teams_query("MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-upcoming-1",
            competition="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now + timedelta(hours=2),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    result = run_live_sync(StaticProvider(), competition="MLB")
    assert result.has_live_games is False
    assert result.next_scheduled_start_at is not None
    assert result.next_scheduled_start_at.tzinfo is not None


def test_live_sync_returns_no_upcoming_when_schedule_empty(db_session):
    result = run_live_sync(StaticProvider(), competition="MLB")
    assert result.has_live_games is False
    assert result.next_scheduled_start_at is None


def test_live_sync_keeps_recently_overdue_scheduled_games_hot(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(competition_teams_query("MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-overdue-1",
            competition="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now - timedelta(minutes=20),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    result = run_live_sync(StaticProvider(), competition="MLB")
    assert result.has_live_games is False
    assert result.next_scheduled_start_at is not None
    assert result.next_scheduled_start_at < now


def test_catalog_sync_fails_for_disabled_competition(db_session):
    ensure_competition_settings(db_session)
    row = db_session.get(CompetitionSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    with pytest.raises(ValueError, match="Competition disabled: MLB"):
        run_catalog_sync(StaticProvider(), competition="MLB")


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

    with pytest.raises(RuntimeError, match="No MLS games could be mapped to catalog teams"):
        run_catalog_sync(provider, competition="MLS")
    assert db_session.scalar(select(Game).where(Game.competition == "MLS")) is None


def test_catalog_sync_allows_partial_team_mapping(db_session, monkeypatch):
    monkeypatch.setattr("app.worker.ingest.settings.odds_api_key", "")
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

    result = run_catalog_sync(provider, competition="MLS")

    assert result.games_checked == 2
    assert result.games_updated == 1
    games = db_session.scalars(select(Game).where(Game.competition == "MLS")).all()
    assert [game.external_game_id for game in games] == ["mls-mapped"]


def test_live_sync_promotes_scheduled_game_to_live(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(competition_teams_query("MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-angels-like",
            competition="MLB",
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

    result = run_live_sync(provider, competition="MLB")
    assert result.has_live_games is True
    assert result.games_updated >= 1

    db_session.expire_all()
    game = db_session.scalar(select(Game).where(Game.external_game_id == "mlb-angels-like", Game.competition == "MLB"))
    assert game is not None
    assert game.status == "in_progress"


def test_ingest_persists_and_refreshes_context_label(db_session):
    run_catalog_sync(ContextLabelProvider("NBA Finals - Game 5 · NY leads series 3-1"), competition="NBA")

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-context"))
    assert game is not None
    assert game.context_label == "NBA Finals - Game 5 · NY leads series 3-1"

    run_catalog_sync(ContextLabelProvider("NBA Finals - Game 5 · Series tied 3-3"), competition="NBA")

    db_session.refresh(game)
    assert game.context_label == "NBA Finals - Game 5 · Series tied 3-3"


def test_catalog_cleanup_runs_in_ingest_transaction(db_session):
    now = datetime.now(timezone.utc)
    teams = db_session.scalars(competition_teams_query("NBA").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="old-cleanup-game",
            competition="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now - timedelta(days=3),
            status="final",
            is_final=True,
        )
    )
    db_session.commit()

    result = run_catalog_sync(StaticProvider())

    assert result.games_removed == 1
    assert db_session.scalar(select(Game).where(Game.external_game_id == "old-cleanup-game")) is None


def test_cleanup_failure_rolls_back_entire_catalog_sync(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    teams = db_session.scalars(competition_teams_query("NBA").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="existing-before-cleanup-failure",
            competition="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now,
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    def fail_cleanup(db, now):
        existing = db.scalar(select(Game).where(Game.external_game_id == "existing-before-cleanup-failure"))
        assert existing is not None
        db.delete(existing)
        db.flush()
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr("app.worker.ingest.cleanup_games_outside_window", fail_cleanup)

    with pytest.raises(RuntimeError, match="cleanup failed"):
        run_catalog_sync(make_success_provider())

    assert db_session.scalar(select(Game).where(Game.external_game_id == "game-1")) is None
    assert db_session.scalar(select(Game).where(Game.external_game_id == "existing-before-cleanup-failure")) is not None


def test_alert_evaluation_failure_rolls_back_catalog_writes(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.worker.ingest.evaluate_and_record_alerts",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("alert evaluation failed")),
    )

    with pytest.raises(RuntimeError, match="alert evaluation failed"):
        run_catalog_sync(make_success_provider())

    assert db_session.scalar(select(Game).where(Game.external_game_id == "game-1")) is None
