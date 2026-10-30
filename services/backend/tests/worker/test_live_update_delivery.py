import asyncio
import threading

import pytest

from app.schemas.schedule import ScheduleSnapshot
from app.schemas.update import GameUpdateEvent
from app.services import worker_schedule
from app.services.game_feed import game_feed_cache
from app.services.live_updates import game_updates
from app.worker import updates


def test_worker_notifies_on_api_event_loop_after_invalidating_cache(monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(updates, "event_loop", loop)
        calls = []
        api_thread = threading.get_ident()
        monkeypatch.setattr(game_feed_cache, "invalidate", lambda: calls.append("invalidate"))
        def publish(event):
            assert threading.get_ident() == api_thread
            assert event == GameUpdateEvent(competition="NCAAB")
            calls.append("publish")
        monkeypatch.setattr(game_updates, "publish", publish)
        assert await asyncio.to_thread(updates.notify_games_changed, "NCAAB")
        await asyncio.sleep(0)
        assert calls == ["invalidate", "publish"]
    asyncio.run(scenario())


def test_schedule_report_replaces_memory_without_network_or_game_notifications(monkeypatch):
    def unexpected(*args):
        raise AssertionError("Schedule reports must not invalidate games")
    monkeypatch.setattr(game_feed_cache, "invalidate", unexpected)
    monkeypatch.setattr(game_updates, "publish", unexpected)
    snapshot = ScheduleSnapshot(reported_at="2026-10-24T12:00:00Z", next_catalog_at="2026-10-24T18:00:00Z", jobs=[])
    assert updates.notify_schedule(snapshot)
    assert worker_schedule.snapshot is snapshot


def test_saved_odds_refresh_cached_feed_and_publish_once(db_session, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.db.models import Game, Team
    from app.services.competitions import competition_teams_query
    from app.worker import odds, odds_sync, scheduler

    now = datetime.now(timezone.utc)
    home, away = db_session.scalars(competition_teams_query("NBA").order_by(Team.id).limit(2)).all()
    game = Game(
        external_game_id="odds-notification", competition="NBA", home_team_id=home.id,
        away_team_id=away.id, scheduled_start_time=now + timedelta(hours=2),
        status="scheduled", is_odds_eligible=True,
    )
    db_session.add(game)
    db_session.commit()
    game_id = game.id
    snapshot = odds.OddsSnapshot(
        outcomes=(odds.OddsOutcome("home", home.name, 0, -145, "home"),),
        bookmaker="Test Book", last_update=now,
    )
    index = {odds.game_key(home.name, away.name): [snapshot]}
    monkeypatch.setattr(odds_sync, "_reserve_credit", lambda *_: "allowed")
    monkeypatch.setattr(odds, "fetch_odds_with_usage", lambda _: odds.OddsProviderResult(index))
    before = game_feed_cache.get()
    assert next(g for g in before if g.id == game_id).odds is None
    db_session.close()

    async def scenario():
        events = []
        monkeypatch.setattr(updates, "event_loop", asyncio.get_running_loop())
        monkeypatch.setattr(game_updates, "publish", events.append)
        first = await asyncio.to_thread(scheduler._run_odds_sync_job, "NBA", now)
        await asyncio.sleep(0)
        assert first.odds_snapshots_created == 1
        after = game_feed_cache.get()
        assert after is not before
        assert next(g for g in after if g.id == game_id).odds.bookmaker == "Test Book"
        second = await asyncio.to_thread(scheduler._run_odds_sync_job, "NBA", now)
        await asyncio.sleep(0)
        assert second.odds_snapshots_created == 0
        assert game_feed_cache.get() is after
        assert events == [GameUpdateEvent(competition="NBA")]

    asyncio.run(scenario())


@pytest.mark.parametrize("outcome", [
    "fetched", "fetch_failed", "quota_failed", "budget_limited", "missing_api_key", "no_eligible_games",
])
def test_odds_without_changes_do_not_notify(monkeypatch, outcome):
    from datetime import datetime, timezone

    from app.worker import scheduler

    calls = []
    result = scheduler.OddsSyncResult("NBA", 1, 0, outcome=outcome)
    monkeypatch.setattr(scheduler, "run_odds_sync", lambda *_: result)
    monkeypatch.setattr(updates, "notify_games_changed", calls.append)
    assert scheduler._run_odds_sync_job("NBA", datetime.now(timezone.utc)) is result
    assert calls == []
