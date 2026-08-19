from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, Team
from worker.ingest import run_catalog_sync, run_live_sync

from ingest_support import (
    RecordingCatalogProvider,
    RepeatMatchupProvider,
    StaticProvider,
    make_game,
    make_snapshot,
    make_success_provider,
)


def test_ingest_persists_current_odds(db_session, monkeypatch):
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): make_snapshot(
                away_label="Atlanta Hawks",
                away_price=110,
                home_label="Boston Celtics",
                home_price=-130,
                last_update=datetime.now(timezone.utc),
            )
        },
    )

    result = run_catalog_sync(make_success_provider())
    assert result["status"] == "success"

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-1"))
    assert game is not None
    odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert odds is not None
    assert [(item.team_side, item.price_american) for item in odds.outcomes] == [("away", 110), ("home", -130)]


def test_ingest_matches_repeat_matchup_odds_by_commence_time(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first_start = now + timedelta(hours=2)
    second_start = now + timedelta(days=2, hours=2)
    provider = RepeatMatchupProvider(first_start=first_start, second_start=second_start)
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=120, home_label="Boston Celtics", home_price=-140, bookmaker="FanDuel", last_update=now, commence_time=first_start),
                make_snapshot(away_label="Atlanta Hawks", away_price=175, home_label="Boston Celtics", home_price=-210, bookmaker="FanDuel", last_update=now, commence_time=second_start),
            ]
        },
    )

    result = run_catalog_sync(provider)
    assert result["status"] == "success"

    first_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-1"))
    second_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-2"))
    assert first_game is not None
    assert second_game is not None

    first_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first_game.id))
    second_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second_game.id))
    assert first_odds is not None
    assert second_odds is None
    assert [(item.team_side, item.price_american) for item in first_odds.outcomes] == [("away", 120), ("home", -140)]


def test_ingest_does_not_apply_far_away_matchup_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first_start = now + timedelta(hours=2)
    second_start = now + timedelta(days=2, hours=2)
    provider = RepeatMatchupProvider(first_start=first_start, second_start=second_start)
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=122, home_label="Boston Celtics", home_price=-145, bookmaker="FanDuel", last_update=now, commence_time=first_start)
            ]
        },
    )

    result = run_catalog_sync(provider)
    assert result["status"] == "success"

    first_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-1"))
    second_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-2"))
    assert first_game is not None
    assert second_game is not None

    first_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first_game.id))
    second_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second_game.id))
    assert first_odds is not None
    assert second_odds is None


def test_ingest_expected_odds_calls_tracks_refresh_decision(db_session, monkeypatch):
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr("worker.ingest.fetch_odds_index", lambda league: {})

    result = run_catalog_sync(make_success_provider())
    assert result["status"] == "success"

    assert result["next_poll_seconds"] > 0


def test_catalog_sync_creates_single_pregame_odds_snapshot(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [make_game(external_game_id="game-catalog", home_external_team_id="1", away_external_team_id="2", scheduled_start_time=now + timedelta(hours=4), status="scheduled")]
    )

    odds_fetch_count = {"count": 0}

    def _fake_odds_index(league):
        odds_fetch_count["count"] += 1
        return {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=110, home_label="Boston Celtics", home_price=-130, last_update=now, commence_time=now + timedelta(hours=4))
            ]
        }

    monkeypatch.setattr("worker.ingest.fetch_odds_index", _fake_odds_index)

    first = run_catalog_sync(provider)
    second = run_catalog_sync(provider)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert first["odds_snapshots_created"] == 1
    assert second["odds_snapshots_created"] == 0


def test_catalog_sync_uses_fixed_horizon_even_with_existing_games(db_session, monkeypatch):
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    mlb_teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc())).all()
    db_session.add(
        Game(
            external_game_id="mlb-existing",
            league="MLB",
            home_team_id=mlb_teams[0].id,
            away_team_id=mlb_teams[1].id,
            scheduled_start_time=now + timedelta(days=2),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    provider = RecordingCatalogProvider(now + timedelta(days=3))
    monkeypatch.setattr("worker.ingest.datetime", type("FixedDateTime", (), {"now": staticmethod(lambda tz=None: now)}))
    monkeypatch.setattr("worker.planner.datetime", type("FixedDateTime", (), {"now": staticmethod(lambda tz=None: now)}))

    result = run_catalog_sync(provider, league="MLB")

    assert result["status"] == "success"
    assert provider.requests == [
        "20260617",
        "20260618",
        "20260619",
        "20260620",
        "20260621",
        "20260622",
        "20260623",
        "20260624",
        "20260625",
    ]


def test_live_sync_does_not_fetch_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(
        Game(
            external_game_id="game-live-only",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now,
            status="live",
            is_final=False,
        )
    )
    db_session.commit()

    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-live-only",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=now,
                status="in_progress",
                home_score=101,
                away_score=99,
                period=4,
                clock="01:15",
            )
        ]
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("odds should not be fetched in live sync")),
    )

    result = run_live_sync(provider)
    assert result["status"] == "success"
    assert result["games_updated"] >= 1


def test_catalog_sync_skips_odds_when_disabled(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [make_game(external_game_id="game-no-odds", home_external_team_id="1", away_external_team_id="2", scheduled_start_time=now + timedelta(hours=4), status="scheduled")]
    )

    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("odds should not be fetched when disabled")),
    )

    result = run_catalog_sync(provider)
    assert result["status"] == "success"
    assert result["odds_candidates"] == 0
    assert result["odds_snapshots_created"] == 0


def test_nfl_preseason_catalog_sync_skips_odds_request(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-nfl-preseason",
                home_external_team_id="2",
                away_external_team_id="12",
                scheduled_start_time=now + timedelta(hours=4),
                status="scheduled",
                season_slug="preseason",
                season_week=2,
                context_label="Preseason · Week 2",
            )
        ]
    )
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("preseason must not fetch NFL odds")),
    )

    result = run_catalog_sync(provider, league="NFL")

    assert result["status"] == "success"
    assert result["odds_candidates"] == 0
    assert result["odds_snapshots_created"] == 0
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-nfl-preseason"))
    assert game is not None
    assert game.context_label == "Preseason · Week 2"


def test_nfl_catalog_sync_only_persists_regular_season_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    preseason_start = now + timedelta(hours=2)
    regular_start = now + timedelta(hours=4)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-nfl-preseason-odds",
                home_external_team_id="2",
                away_external_team_id="12",
                scheduled_start_time=preseason_start,
                status="scheduled",
                season_slug="preseason",
            ),
            make_game(
                external_game_id="game-nfl-regular-odds",
                home_external_team_id="2",
                away_external_team_id="12",
                scheduled_start_time=regular_start,
                status="scheduled",
                season_slug="regular-season",
            ),
        ]
    )
    calls: list[str] = []

    def _fake_odds_index(league: str):
        calls.append(league)
        return {
            ("buffalo bills", "kansas city chiefs"): [
                make_snapshot(
                    away_label="Kansas City Chiefs",
                    away_price=115,
                    home_label="Buffalo Bills",
                    home_price=-135,
                    last_update=now,
                    commence_time=regular_start,
                )
            ]
        }

    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr("worker.ingest.fetch_odds_index", _fake_odds_index)

    result = run_catalog_sync(provider, league="NFL")

    assert result["status"] == "success"
    assert result["odds_candidates"] == 1
    assert result["odds_snapshots_created"] == 1
    assert calls == ["NFL"]
    preseason = db_session.scalar(select(Game).where(Game.external_game_id == "game-nfl-preseason-odds"))
    regular = db_session.scalar(select(Game).where(Game.external_game_id == "game-nfl-regular-odds"))
    assert preseason is not None
    assert regular is not None
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == preseason.id)) is None
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == regular.id)) is not None


def test_world_cup_catalog_sync_persists_three_way_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-world-cup-scheduled",
                home_external_team_id="660",
                away_external_team_id="203",
                scheduled_start_time=now + timedelta(hours=3),
                status="scheduled",
                is_final=False,
            )
        ]
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("united states", "mexico"): [
                make_snapshot(
                    away_label="Mexico",
                    away_price=180,
                    home_label="United States",
                    home_price=160,
                    draw_price=210,
                    last_update=now,
                    commence_time=now + timedelta(hours=3),
                )
            ]
        },
    )

    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert result["odds_snapshots_created"] == 1

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-world-cup-scheduled"))
    assert game is not None
    odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert odds is not None
    assert [(item.outcome_key, item.price_american) for item in odds.outcomes] == [
        ("mexico", 180),
        ("draw", 210),
        ("united_states", 160),
    ]
