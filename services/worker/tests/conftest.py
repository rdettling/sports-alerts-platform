import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = Path(__file__).parent / "worker_test.db"
os.environ.update(
    {
        "APP_NAME": "sports-alerts-api-test",
        "API_HOST": "127.0.0.1",
        "API_PORT": "8000",
        "DATABASE_URL": f"sqlite+pysqlite:///{TEST_DB_PATH}",
        "JWT_SECRET_KEY": "test-secret",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRE_MINUTES": "10080",
        "CORS_ALLOW_ORIGINS": "http://localhost:5173",
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
        "DEV_MODE": "false",
        "INGEST_INTERVAL_LIVE_SECONDS": "60",
        "INGEST_INTERVAL_ACTIVE_SECONDS": "300",
        "INGEST_INTERVAL_IDLE_SECONDS": "900",
        "DELIVERY_TICK_SECONDS": "30",
        "NBA_PROVIDER": "espn",
        "DELIVERY_MODE": "log",
        "FROM_EMAIL": "alerts@test.local",
        "RESEND_API_KEY": "test-key",
        "RESEND_API_URL": "https://api.resend.com/emails",
    }
)

from app.db.models import Base, Team  # noqa: E402
from worker.ingest import SessionLocal  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    db.add_all(
        [
            Team(external_team_id="1610612737", league="NBA", name="Atlanta Hawks", abbreviation="ATL"),
            Team(external_team_id="1610612738", league="NBA", name="Boston Celtics", abbreviation="BOS"),
        ]
    )
    db.commit()
    db.close()
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
