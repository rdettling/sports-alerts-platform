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
        "MAGIC_LINK_TTL_MINUTES": "15",
        "MAGIC_LINK_COOLDOWN_SECONDS": "60",
        "MAGIC_LINK_MAX_REQUESTS_PER_HOUR": "5",
        "WEB_BASE_URL": "http://localhost:5173",
        "CORS_ALLOW_ORIGINS": "http://localhost:5173",
        "ODDS_API_KEY": "test-odds-key",
        "ODDS_API_BASE_URL": "https://api.the-odds-api.com/v4/sports",
        "ODDS_PROVIDER": "the_odds_api",
        "ODDS_API_SPORT_KEY": "basketball_nba",
        "ODDS_API_SPORT_KEY_NBA": "basketball_nba",
        "ODDS_API_SPORT_KEY_MLB": "baseball_mlb",
        "ODDS_API_REGIONS": "us",
        "ODDS_API_MARKET": "h2h",
        "ODDS_API_FORMAT": "american",
        "ODDS_API_TIMEOUT_SECONDS": "6",
        "ODDS_API_CACHE_SECONDS": "60",
        "ODDS_ENABLED": "true",
        "ODDS_REFRESH_SECONDS": "21600",
        "CATALOG_SYNC_INTERVAL_SECONDS": "43200",
        "LIVE_SYNC_INTERVAL_SECONDS": "120",
        "NBA_LIVE_SYNC_INTERVAL_SECONDS": "120",
        "MLB_LIVE_SYNC_INTERVAL_SECONDS": "300",
        "LIVE_SYNC_PREGAME_RETRY_SECONDS": "600",
        "ODDS_PREGAME_WINDOW_HOURS": "24",
        "TELEMETRY_RAW_EVENTS_ENABLED": "true",
        "DEV_MODE": "false",
        "INGEST_LIVE_INTERVAL_SECONDS": "120",
        "INGEST_PREGAME_HOT_INTERVAL_SECONDS": "900",
        "INGEST_PREGAME_COLD_INTERVAL_SECONDS": "3600",
        "INGEST_OFF_INTERVAL_SECONDS": "43200",
        "INGEST_PREGAME_HOT_WINDOW_MINUTES": "90",
        "INGEST_PREGAME_COLD_WINDOW_HOURS": "24",
        "INGEST_HEARTBEAT_SECONDS": "3600",
        "SCHEDULER_TICK_SECONDS": "60",
        "DELIVERY_IDLE_SECONDS": "300",
        "DELIVERY_ACTIVE_SECONDS": "60",
        "CLEANUP_INTERVAL_SECONDS": "21600",
        "GAMES_RETENTION_PAST_HOURS": "36",
        "GAMES_RETENTION_FUTURE_DAYS": "7",
        "JOB_MAX_RETRIES": "5",
        "JOB_RETRY_BASE_SECONDS": "30",
        "JOB_RETRY_MAX_BACKOFF_SECONDS": "3600",
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
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    db.add_all(
        [
            Team(external_team_id="1", league="NBA", name="Atlanta Hawks", abbreviation="ATL"),
            Team(external_team_id="2", league="NBA", name="Boston Celtics", abbreviation="BOS"),
            Team(external_team_id="10", league="MLB", name="New York Yankees", abbreviation="NYY"),
            Team(external_team_id="2", league="MLB", name="Boston Red Sox", abbreviation="BOS"),
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
