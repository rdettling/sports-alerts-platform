from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, OddsApiDailyUsage, Team
from app.worker import odds, odds_sync


def _game(db_session, *, competition="NBA", start, eligible=True):
    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
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


def test_odds_sync_prices_all_eligible_games_with_one_feed(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    first, home, away = _game(db_session, start=now + timedelta(hours=4))
    second, _, _ = _game(db_session, start=now + timedelta(hours=4, minutes=30))
    calls = []
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: (True, False))
    snapshot = odds.OddsSnapshot(outcomes=(), bookmaker="Test", last_update=now)
    monkeypatch.setattr(
        odds,
        "fetch_odds_with_usage",
        lambda competition: calls.append(competition) or odds.OddsProviderResult(
            {odds.game_key(home.name, away.name): [snapshot]}
        ),
    )

    result = odds_sync.run_odds_sync("NBA", now)

    assert calls == ["NBA"]
    assert result.games_checked == 2
    assert result.odds_snapshots_created == 2
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first.id))
    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second.id))


def test_unmatched_games_remain_eligible_for_the_next_sweep(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    game, _, _ = _game(db_session, start=now + timedelta(hours=30))
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: (True, False))
    monkeypatch.setattr(odds, "fetch_odds_with_usage", lambda _: odds.OddsProviderResult({}))

    odds_sync.run_odds_sync("NBA", now)

    assert db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id)) is None
    assert odds_sync.has_eligible_games("NBA", now + timedelta(hours=12)) is True


def test_failed_paid_request_is_retried_at_the_next_sweep(db_session, monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    game, home, away = _game(db_session, start=now + timedelta(hours=30))
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: (True, False))
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


def test_daily_cap_blocks_paid_requests_until_rollover(db_session):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    db_session.add(OddsApiDailyUsage(usage_date=now.date(), credits_used=16))
    db_session.commit()

    assert odds_sync._reserve_credit(db_session, now) == (False, True)
