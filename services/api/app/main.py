import logging
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import SessionLocal
from app.routers.auth import router as auth_router
from app.routers.alerts import router as alerts_router
from app.routers.follows import router as follows_router
from app.routers.games import router as games_router
from app.routers.health import router as health_router
from app.routers.leagues import router as leagues_router
from app.routers.preferences import router as preferences_router
from app.routers.teams import router as teams_router
from app.routers.ops import router as ops_router
from app.logging_filters import SuppressLowSignalAccessLogsFilter
from app.services.seed import ensure_bootstrap_admin, seed_teams_if_empty

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
access_logger = logging.getLogger("uvicorn.access")
if not any(isinstance(log_filter, SuppressLowSignalAccessLogsFilter) for log_filter in access_logger.filters):
    access_logger.addFilter(SuppressLowSignalAccessLogsFilter())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    started_at = monotonic()
    logger.info("Startup seed begin")
    db = SessionLocal()
    try:
        seed_teams_if_empty(db)
        ensure_bootstrap_admin(db, settings.bootstrap_admin_email)
        elapsed_ms = int((monotonic() - started_at) * 1000)
        logger.info("Startup seed complete elapsed_ms=%s", elapsed_ms)
    finally:
        db.close()
    yield


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
app.include_router(leagues_router)
app.include_router(teams_router)
app.include_router(games_router)
app.include_router(follows_router)
app.include_router(preferences_router)
app.include_router(alerts_router)
app.include_router(ops_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    messages = [error.get("msg", "Invalid request") for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": ", ".join(messages)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
