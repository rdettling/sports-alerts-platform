import os
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

TEST_DIRECTORY = TemporaryDirectory(prefix="sports-alerts-tests-")
TEST_DB_PATH = Path(TEST_DIRECTORY.name) / "test.db"
os.environ.update(
    {
        "ODDS_API_KEY": "test-odds-key",
        "APP_NAME": "sports-alerts-api-test",
        "DATABASE_URL": f"sqlite+pysqlite:///{TEST_DB_PATH}",
        "JWT_SECRET_KEY": "test-secret",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRE_MINUTES": "10080",
        "MAGIC_LINK_TTL_MINUTES": "15",
        "MAGIC_LINK_COOLDOWN_SECONDS": "60",
        "MAGIC_LINK_MAX_REQUESTS_PER_HOUR": "5",
        "WEB_BASE_URL": "http://localhost:5173",
        "CORS_ALLOW_ORIGINS": "http://localhost:5173",
        "DELIVERY_MODE": "log",
        "FROM_EMAIL": "alerts@example.com",
        "RESEND_API_KEY": "test-resend-key",
        "RESEND_API_URL": "https://api.resend.com/emails",
        "VAPID_PUBLIC_KEY": "test-public-key",
        "VAPID_PRIVATE_KEY": "test-private-key",
        "VAPID_SUBJECT": "mailto:alerts@example.com",
    }
)

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.services import worker_schedule  # noqa: E402
from app.services.game_feed import game_feed_cache  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def close_database():
    yield
    engine.dispose()
    TEST_DIRECTORY.cleanup()


@pytest.fixture(autouse=True)
def reset_db(monkeypatch):
    @asynccontextmanager
    async def idle_worker():
        yield ()

    monkeypatch.setattr("app.main.running_worker", idle_worker)
    monkeypatch.setattr("app.worker.scheduler.create_daily_backup", lambda: None)
    worker_schedule.snapshot = None
    game_feed_cache.invalidate()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
