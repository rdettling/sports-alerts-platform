import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).parent / "test.db"
os.environ.update(
    {
        "APP_NAME": "sports-alerts-api-test",
        "API_HOST": "127.0.0.1",
        "API_PORT": "8000",
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
        "ODDS_API_KEY": "test-odds-key",
        "ODDS_API_BASE_URL": "https://api.the-odds-api.com/v4/sports",
        "ODDS_PROVIDER": "the_odds_api",
        "ODDS_API_SPORT_KEY": "basketball_nba",
        "ODDS_API_REGIONS": "us",
        "ODDS_API_MARKET": "h2h",
        "ODDS_API_FORMAT": "american",
        "ODDS_API_TIMEOUT_SECONDS": "6",
        "ODDS_API_CACHE_SECONDS": "60",
        "ODDS_ENABLED": "true",
        "ODDS_REFRESH_SECONDS": "5400",
        "DEV_MODE": "true",
    }
)

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
