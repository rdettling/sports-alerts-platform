import secrets

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas.update import GameUpdateEvent
from app.services.live_updates import game_updates

router = APIRouter(tags=["updates"])


@router.get("/updates/games")
async def stream_game_updates() -> StreamingResponse:
    queue = game_updates.subscribe()
    return StreamingResponse(
        game_updates.events(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/internal/updates/games", status_code=status.HTTP_204_NO_CONTENT)
async def publish_game_update(
    event: GameUpdateEvent,
    live_update_secret: str | None = Header(default=None, alias="X-Live-Update-Secret"),
) -> Response:
    configured_secret = settings.live_update_secret
    if not configured_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live updates are not configured",
        )
    if live_update_secret is None or not secrets.compare_digest(
        live_update_secret,
        configured_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid live update secret",
        )

    game_updates.publish(event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
