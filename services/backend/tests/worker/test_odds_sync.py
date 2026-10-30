import logging
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError

import pytest

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, OddsApiDailyUsage, Team
from app.services.competitions import competition_teams_query
from app.worker import odds, odds_sync


def _game(db_session, *, competition="NBA", start, eligible=True):
    teams = db_session.scalars(competition_teams_query(competition).order_by(Team.id.asc()).limit(2)).all()
    game = Game(
        external_game_id=f"odds-sync-{competition}-{start.timestamp()}-{eligible}",
        competition=competition,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=start,
        status="scheduled",
        is_odds_eligible=eligible,
    )
    db_session.add(game)
    db_session.commit()
    return game, teams[0], teams[1]


@pytest.mark.parametrize("competition", ["NBA", "NCAAB"])
def test_odds_sync_prices_all_eligible_games_with_one_feed(db_session, monkeypatch, competition):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    first, home, away = _game(db_session, competition=competition, start=now + timedelta(hours=4))
    second, _, _ = _game(db_session, competition=competition, start=now + timedelta(hours=4, minutes=30))
    calls = []
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: "allowed")
    snapshot = odds.OddsSnapshot(outcomes=(), bookmaker="Test", last_update=now)
    monkeypatch.setattr(
        odds,
        "fetch_odds_with_usage",
        lambda competition: calls.append(competition) or odds.OddsProviderResult(
            {odds.game_key(home.name, away.name): [snapshot]}
        ),
    )

    result = odds_sync.run_odds_sync(competition, now)

    assert calls == [competition]
    assert result.games_checked == 2
    assert result.odds_snapshots_created == 2
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first.id))
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second.id))


def test_unmatched_games_remain_eligible_for_the_next_sweep(db_session, monkeypatch, caplog):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    game, _, _ = _game(db_session, start=now + timedelta(hours=30))
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: "allowed")
    monkeypatch.setattr(odds, "fetch_odds_with_usage", lambda _: odds.OddsProviderResult({}))

    with caplog.at_level(logging.INFO):
        result = odds_sync.run_odds_sync("NBA", now)

    assert result.outcome == "fetched"
    assert "provider_moneyline_matchups=0" in caplog.text
    assert "unmatched_games=1" in caplog.text
    assert f"'game_id': {game.id}" in caplog.text
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id)) is None
    assert odds_sync.has_eligible_games("NBA", now + timedelta(hours=12)) is True


def test_failed_paid_request_is_retried_at_the_next_sweep(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    game, home, away = _game(db_session, start=now + timedelta(hours=30))
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: "allowed")
    monkeypatch.setattr(odds, "fetch_odds_with_usage", lambda _: (_ for _ in ()).throw(RuntimeError()))

    odds_sync.run_odds_sync("NBA", now)
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id)) is None

    snapshot = odds.OddsSnapshot(outcomes=(), bookmaker="Test", last_update=now)
    monkeypatch.setattr(
        odds,
        "fetch_odds_with_usage",
        lambda _: odds.OddsProviderResult({odds.game_key(home.name, away.name): [snapshot]}),
    )
    odds_sync.run_odds_sync("NBA", now + timedelta(hours=12))

    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id)) is not None


def test_ineligible_games_do_not_trigger_a_paid_request(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    _game(db_session, competition="NFL", start=now + timedelta(hours=4), eligible=False)
    monkeypatch.setattr(
        odds,
        "fetch_odds_with_usage",
        lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )

    result = odds_sync.run_odds_sync("NFL", now)

    assert result.games_checked == 0


def test_daily_cap_blocks_paid_requests_until_rollover(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    db_session.add(OddsApiDailyUsage(usage_date=now.date(), credits_used=16))
    db_session.commit()

    assert odds_sync._reserve_credit("NBA", now) == "budget_limited"
    monkeypatch.setattr(odds, "fetch_quota_status", lambda: odds.OddsProviderResult({}, 10, 100))
    tomorrow = now + timedelta(days=1)
    assert odds_sync._reserve_credit("NBA", tomorrow) == "allowed"
    assert db_session.get(OddsApiDailyUsage, tomorrow.date()).credits_used == 1


def test_provider_requests_do_not_hold_database_connections(db_session, monkeypatch):
    from app.db.session import engine

    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    _game(db_session, start=now + timedelta(hours=2))
    db_session.close()
    calls = []

    def quota():
        assert engine.pool.checkedout() == 0
        calls.append("quota")
        return odds.OddsProviderResult({}, credits_used=10, credits_remaining=100)

    def prices(competition):
        assert engine.pool.checkedout() == 0
        calls.append(competition)
        return odds.OddsProviderResult({})

    monkeypatch.setattr(odds, "fetch_quota_status", quota)
    monkeypatch.setattr(odds, "fetch_odds_with_usage", prices)
    odds_sync.run_odds_sync("NBA", now)
    assert calls == ["quota", "NBA"]
    assert db_session.get(OddsApiDailyUsage, now.date()).credits_used == 1


@pytest.mark.parametrize("stage", ["quota", "prices"])
@pytest.mark.parametrize("error", [
    TimeoutError("secret-request-url"),
    URLError(TimeoutError("secret-request-url")),
    HTTPError("secret-request-url", 429, "Too Many Requests", {}, None),
])
def test_request_failures_identify_stage_without_leaking_urls(
    db_session, monkeypatch, caplog, stage, error,
):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    _game(db_session, start=now + timedelta(hours=2))

    def fail(*args, **kwargs):
        raise error

    if stage == "prices":
        monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: "allowed")
    monkeypatch.setattr(odds, "urlopen", fail)

    result = odds_sync.run_odds_sync("NBA", now)

    assert result.outcome == ("quota_failed" if stage == "quota" else "fetch_failed")
    assert result.games_checked == 1
    assert f"stage={stage}" in caplog.text
    assert f"error_type={type(error).__name__}" in caplog.text
    assert "competition=NBA" in caplog.text
    if isinstance(error, URLError) and isinstance(error.reason, TimeoutError):
        assert "reason_type=TimeoutError" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "timeout_seconds=6" in caplog.text
    assert f"http_status={429 if isinstance(error, HTTPError) else None}" in caplog.text
    assert "secret-request-url" not in caplog.text


def test_unmatched_sample_is_bounded(db_session, monkeypatch, caplog):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    for hour in range(1, 8):
        _game(db_session, start=now + timedelta(hours=hour))
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: "allowed")
    monkeypatch.setattr(odds, "fetch_odds_with_usage", lambda _: odds.OddsProviderResult({}))

    with caplog.at_level(logging.INFO):
        odds_sync.run_odds_sync("NBA", now)

    assert "unmatched_games=7" in caplog.text
    assert caplog.text.count("'game_id':") == 5


def test_missing_key_is_distinct_from_no_eligible_games(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(odds_sync.settings, "odds_api_key", "")
    assert odds_sync.run_odds_sync("NBA", now).outcome == "no_eligible_games"
    _game(db_session, start=now + timedelta(hours=2))
    result = odds_sync.run_odds_sync("NBA", now)
    assert result.outcome == "missing_api_key"
    assert result.games_checked == 1
    assert db_session.get(OddsApiDailyUsage, now.date()) is None


def test_provider_reserve_blocks_paid_request_and_records_balance(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    _game(db_session, start=now + timedelta(hours=2))
    monkeypatch.setattr(odds, "fetch_quota_status", lambda: odds.OddsProviderResult({}, 475, 25))

    def unexpected(*args):
        raise AssertionError("must not use reserved provider credits")

    monkeypatch.setattr(odds, "fetch_odds_with_usage", unexpected)
    assert odds_sync.run_odds_sync("NBA", now).outcome == "budget_limited"
    usage = db_session.get(OddsApiDailyUsage, now.date())
    assert usage.credits_used == 0
    assert usage.provider_credits_remaining == 25
