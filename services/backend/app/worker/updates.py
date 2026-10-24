import asyncio

from app.schemas.schedule import ScheduleSnapshot
from app.schemas.update import GameUpdateEvent
from app.services import worker_schedule
from app.services.game_feed import game_feed_cache
from app.services.live_updates import game_updates

# Bound by the single backend's lifespan before its scheduler starts.
event_loop: asyncio.AbstractEventLoop | None = None


def notify_games_changed(competition: str) -> bool:
    game_feed_cache.invalidate()
    if event_loop is None:
        return False
    event_loop.call_soon_threadsafe(game_updates.publish, GameUpdateEvent(competition=competition))
    return True


def notify_schedule(snapshot: ScheduleSnapshot) -> bool:
    worker_schedule.snapshot = snapshot
    return True
