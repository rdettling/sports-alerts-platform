from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz(request: Request) -> dict[str, str]:
    if not all(thread.is_alive() for thread in request.app.state.worker_threads):
        raise HTTPException(status_code=503, detail="Background worker stopped")
    return {"status": "ok"}
