from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, Team
from app.services.competitions import competition_teams_query
from app.worker.ingest import run_catalog_sync, run_live_sync

from ingest_support import (
    RecordingCatalogProvider,
    RepeatMatchupProvider,
    StaticProvider,
    make_game,
    make_snapshot,
    make_success_provider,
)


def test_ingest_persists_current_odds(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
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
    assert result.odds_snapshots_created == 1

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-1"))
    assert game is not None
    odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert odds is not None
    assert [(item.team_side, item.price_american) for item in odds.outcomes] == [("away", 110), ("home", -130)]


def test_fbs_catalog_sync_persists_odds_for_long_team_name(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-fbs-long-team-name",
                home_external_team_id="66",
                away_external_team_id="fcs-999",
                home_team_name="Iowa State Cyclones",
                home_team_abbreviation="ISU",
                away_team_name="Southeast Missouri State Redhawks",
                away_team_abbreviation="SEMO",
                scheduled_start_time=now + timedelta(hours=3),
                status="scheduled",
            )
        ]
    )
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
            ("iowa state cyclones", "southeast missouri state redhawks"): make_snapshot(
                away_label="Southeast Missouri State Redhawks",
                away_price=2400,
                home_label="Iowa State Cyclones",
                home_price=-10000,
                last_update=now,
            )
        },
    )

    result = run_catalog_sync(provider, competition="FBS")

    assert result.odds_snapshots_created == 1
    game = db_session.scalar(
        select(Game).where(Game.external_game_id == "game-fbs-long-team-name")
    )
    assert game is not None
    current_odds = db_session.scalar(
        select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id)
    )
    assert current_odds is not None
    assert [item.outcome_key for item in current_odds.outcomes] == [
        "southeast_missouri_state_redhawks",
        "iowa_state_cyclones",
    ]


def test_la_liga_catalog_sync_persists_game_and_three_way_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-la-liga-scheduled",
                home_external_team_id="83",
                away_external_team_id="86",
                scheduled_start_time=now + timedelta(hours=3),
                status="scheduled",
            )
        ]
    )
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
            ("barcelona", "real madrid"): [
                make_snapshot(
                    away_label="Real Madrid",
                    away_price=180,
                    home_label="Barcelona",
                    home_price=150,
                    draw_price=220,
                    last_update=now,
                    commence_time=now + timedelta(hours=3),
                )
            ]
        },
    )

    result = run_catalog_sync(provider, competition="LA_LIGA")

    assert result.games_updated == 1
    assert result.odds_snapshots_created == 1
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-la-liga-scheduled"))
    assert game is not None
    assert game.competition == "LA_LIGA"
    current_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert current_odds is not None
    assert [(item.team_side, item.price_american) for item in current_odds.outcomes] == [
        ("away", 180),
        (None, 220),
        ("home", 150),
    ]


def test_premier_competition_catalog_sync_persists_game_and_three_way_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-premier-competition-scheduled",
                home_external_team_id="359",
                away_external_team_id="364",
                scheduled_start_time=now + timedelta(hours=3),
                status="scheduled",
            )
        ]
    )
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
            ("arsenal", "liverpool"): [
                make_snapshot(
                    away_label="Liverpool",
                    away_price=190,
                    home_label="Arsenal",
                    home_price=145,
                    draw_price=230,
                    last_update=now,
                    commence_time=now + timedelta(hours=3),
                )
            ]
        },
    )

    result = run_catalog_sync(provider, competition="PREMIER_LEAGUE")

    assert result.games_updated == 1
    assert result.odds_snapshots_created == 1
    game = db_session.scalar(
        select(Game).where(Game.external_game_id == "game-premier-competition-scheduled")
    )
    assert game is not None
    assert game.competition == "PREMIER_LEAGUE"
    current_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert current_odds is not None
    assert [(item.team_side, item.price_american) for item in current_odds.outcomes] == [
        ("away", 190),
        (None, 230),
        ("home", 145),
    ]


def test_odds_failure_rolls_back_catalog_writes(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: (_ for _ in ()).throw(RuntimeError("odds unavailable")),
    )

    with pytest.raises(RuntimeError, match="odds unavailable"):
        run_catalog_sync(make_success_provider())

    assert db_session.scalar(select(Game).where(Game.external_game_id == "game-1")) is None


def test_ingest_matches_repeat_matchup_odds_by_commence_time(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first_start = now + timedelta(hours=2)
    second_start = now + timedelta(days=2, hours=2)
    provider = RepeatMatchupProvider(first_start=first_start, second_start=second_start)
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=120, home_label="Boston Celtics", home_price=-140, bookmaker="FanDuel", last_update=now, commence_time=first_start),
                make_snapshot(away_label="Atlanta Hawks", away_price=175, home_label="Boston Celtics", home_price=-210, bookmaker="FanDuel", last_update=now, commence_time=second_start),
            ]
        },
    )

    result = run_catalog_sync(provider)
    assert result.odds_snapshots_created == 1

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
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=122, home_label="Boston Celtics", home_price=-145, bookmaker="FanDuel", last_update=now, commence_time=first_start)
            ]
        },
    )

    result = run_catalog_sync(provider)
    assert result.odds_snapshots_created == 1

    first_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-1"))
    second_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-2"))
    assert first_game is not None
    assert second_game is not None

    first_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first_game.id))
    second_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second_game.id))
    assert first_odds is not None
    assert second_odds is None


def test_ingest_reports_odds_candidates(db_session, monkeypatch):
    monkeypatch.setattr("app.worker.odds.fetch_odds_index", lambda competition: {})

    result = run_catalog_sync(make_success_provider())
    assert result.odds_candidates == 1


def test_catalog_sync_creates_single_pregame_odds_snapshot(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [make_game(external_game_id="game-catalog", home_external_team_id="1", away_external_team_id="2", scheduled_start_time=now + timedelta(hours=4), status="scheduled")]
    )

    odds_fetch_count = {"count": 0}

    def _fake_odds_index(competition):
        odds_fetch_count["count"] += 1
        return {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=110, home_label="Boston Celtics", home_price=-130, last_update=now, commence_time=now + timedelta(hours=4))
            ]
        }

    monkeypatch.setattr("app.worker.odds.fetch_odds_index", _fake_odds_index)

    first = run_catalog_sync(provider)
    second = run_catalog_sync(provider)

    assert first.odds_snapshots_created == 1
    assert second.odds_snapshots_created == 0


def test_catalog_sync_uses_fixed_horizon_even_with_existing_games(db_session, monkeypatch):
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    mlb_teams = db_session.scalars(competition_teams_query("MLB").order_by(Team.id.asc())).all()
    db_session.add(
        Game(
            external_game_id="mlb-existing",
            competition="MLB",
            home_team_id=mlb_teams[0].id,
            away_team_id=mlb_teams[1].id,
            scheduled_start_time=now + timedelta(days=2),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    provider = RecordingCatalogProvider(now + timedelta(days=3))
    monkeypatch.setattr("app.worker.ingest.datetime", type("FixedDateTime", (), {"now": staticmethod(lambda tz=None: now)}))

    result = run_catalog_sync(provider, competition="MLB")

    assert result.games_checked == 1
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
            competition="NBA",
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
        "app.worker.odds.fetch_odds_index",
        lambda competition: (_ for _ in ()).throw(AssertionError("odds should not be fetched in live sync")),
    )

    result = run_live_sync(provider)
    assert result.games_updated >= 1


def test_catalog_sync_skips_odds_when_api_key_is_blank(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [make_game(external_game_id="game-no-odds", home_external_team_id="1", away_external_team_id="2", scheduled_start_time=now + timedelta(hours=4), status="scheduled")]
    )

    monkeypatch.setattr("app.worker.ingest.settings.odds_api_key", "")
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: (_ for _ in ()).throw(AssertionError("odds should not be fetched without a key")),
    )

    result = run_catalog_sync(provider)
    assert result.odds_candidates == 0
    assert result.odds_snapshots_created == 0


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
    monkeypatch.setattr(
        "app.worker.odds.fetch_odds_index",
        lambda competition: (_ for _ in ()).throw(AssertionError("preseason must not fetch NFL odds")),
    )

    result = run_catalog_sync(provider, competition="NFL")

    assert result.odds_candidates == 0
    assert result.odds_snapshots_created == 0
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

    def _fake_odds_index(competition: str):
        calls.append(competition)
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

    monkeypatch.setattr("app.worker.odds.fetch_odds_index", _fake_odds_index)

    result = run_catalog_sync(provider, competition="NFL")

    assert result.odds_candidates == 1
    assert result.odds_snapshots_created == 1
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
        "app.worker.odds.fetch_odds_index",
        lambda competition: {
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

    result = run_catalog_sync(provider, competition="WORLD_CUP")
    assert result.odds_snapshots_created == 1

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-world-cup-scheduled"))
    assert game is not None
    odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert odds is not None
    assert [(item.outcome_key, item.price_american) for item in odds.outcomes] == [
        ("mexico", 180),
        ("draw", 210),
        ("united_states", 160),
    ]
