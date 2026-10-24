import asyncio

from app.routers.updates import stream_game_updates
from app.schemas.update import GameUpdateEvent
from app.services.live_updates import LiveUpdateBroadcaster






def test_stream_response_has_sse_headers():
    async def scenario():
        response = await stream_game_updates()
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        await response.body_iterator.aclose()

    asyncio.run(scenario())


def test_broadcaster_sends_events_heartbeats_and_cleans_up():
    async def scenario():
        broadcaster = LiveUpdateBroadcaster()
        queue = broadcaster.subscribe()
        stream = broadcaster.events(queue, heartbeat_seconds=0.001)

        assert await anext(stream) == "retry: 5000\n\n"
        assert await anext(stream) == ": keep-alive\n\n"

        broadcaster.publish(GameUpdateEvent(competition="NBA"))
        assert await anext(stream) == 'event: games\ndata: {"competition":"NBA"}\n\n'

        await stream.aclose()
        assert broadcaster.subscriber_count == 0

    asyncio.run(scenario())


def test_broadcaster_coalesces_bursts_per_subscriber():
    broadcaster = LiveUpdateBroadcaster()
    queue = broadcaster.subscribe()
    try:
        broadcaster.publish(GameUpdateEvent(competition="NBA"))
        broadcaster.publish(GameUpdateEvent(competition="MLB"))

        assert queue.get_nowait() == GameUpdateEvent(competition="NBA")
        assert queue.empty()
    finally:
        broadcaster.unsubscribe(queue)
