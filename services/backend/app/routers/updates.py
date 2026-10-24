from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.live_updates import game_updates

router = APIRouter(tags=["updates"])


@router.get("/updates/games")
async def stream_game_updates() -> StreamingResponse:
    queue = game_updates.subscribe()
    return StreamingResponse(
        game_updates.events(queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
