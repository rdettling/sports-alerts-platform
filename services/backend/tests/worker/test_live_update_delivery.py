import asyncio
import threading

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
