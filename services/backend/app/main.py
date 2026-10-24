import fcntl
import logging
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import SessionLocal, database_path, engine
from app.routers.auth import router as auth_router
from app.routers.alerts import router as alerts_router
from app.routers.follows import router as follows_router
from app.routers.games import router as games_router
from app.routers.health import router as health_router
from app.routers.competitions import router as competitions_router
from app.routers.competition_visibility import router as competition_visibility_router
from app.routers.preferences import router as preferences_router
from app.routers.teams import router as teams_router
from app.routers.updates import router as updates_router
from app.routers.ops import router as ops_router
from app.routers.notifications import router as notifications_router
from app.logging_filters import SuppressLowSignalAccessLogsFilter
from app.worker.runtime import running_worker
from app.services.seed import ensure_bootstrap_admin, ensure_seeded_teams

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
access_logger = logging.getLogger("uvicorn.access")
if not any(isinstance(log_filter, SuppressLowSignalAccessLogsFilter) for log_filter in access_logger.filters):
    access_logger.addFilter(SuppressLowSignalAccessLogsFilter())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with database_path.with_name(database_path.name + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another backend already owns this SQLite database") from None
        try:
            started_at = monotonic()
            logger.info("Startup seed begin")
            with SessionLocal() as db:
                ensure_seeded_teams(db)
                ensure_bootstrap_admin(db, settings.bootstrap_admin_email)
            logger.info("Startup seed complete elapsed_ms=%s", int((monotonic() - started_at) * 1000))
            async with running_worker() as threads:
                app.state.worker_threads = threads
                yield
        finally:
            engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
allowed_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(competitions_router)
app.include_router(competition_visibility_router)
app.include_router(teams_router)
app.include_router(games_router)
app.include_router(follows_router)
app.include_router(preferences_router)
app.include_router(notifications_router)
app.include_router(alerts_router)
app.include_router(ops_router)
app.include_router(updates_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    messages = [error.get("msg", "Invalid request") for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": ", ".join(messages)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
