from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.schemas.update import GameUpdateEvent

HEARTBEAT_INTERVAL_SECONDS = 25
RECONNECT_DELAY_MS = 5_000


class LiveUpdateBroadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[GameUpdateEvent]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue[GameUpdateEvent]:
        queue: asyncio.Queue[GameUpdateEvent] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[GameUpdateEvent]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: GameUpdateEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.empty():
                queue.put_nowait(event)

    async def events(
        self,
        queue: asyncio.Queue[GameUpdateEvent],
        *,
        heartbeat_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
    ) -> AsyncIterator[str]:
        try:
            yield f"retry: {RECONNECT_DELAY_MS}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

                data = json.dumps(event.model_dump(), separators=(",", ":"))
                yield f"event: games\ndata: {data}\n\n"
        finally:
            self.unsubscribe(queue)


game_updates = LiveUpdateBroadcaster()
