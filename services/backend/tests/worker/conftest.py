import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = Path(__file__).parent / "worker_test.db"
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+pysqlite:///{TEST_DB_PATH}",
        "ODDS_API_KEY": "test-odds-key",
        "CATALOG_SYNC_INTERVAL_SECONDS": "43200",
        "DELIVERY_MODE": "log",
        "FROM_EMAIL": "alerts@test.local",
        "RESEND_API_KEY": "test-key",
        "RESEND_API_URL": "https://api.resend.com/emails",
        "VAPID_PRIVATE_KEY": "test-private-key",
        "VAPID_SUBJECT": "mailto:alerts@example.com",
    }
)

from app.db.models import Base, Team  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

TEST_TEAM_SEEDS = [
    ("1", "NBA", "Atlanta Hawks", "ATL"),
    ("2", "NBA", "Boston Celtics", "BOS"),
    ("9", "WNBA", "New York Liberty", "NY"),
    ("17", "WNBA", "Las Vegas Aces", "LV"),
    ("2", "NFL", "Buffalo Bills", "BUF"),
    ("12", "NFL", "Kansas City Chiefs", "KC"),
    ("10", "MLB", "New York Yankees", "NYY"),
    ("2", "MLB", "Boston Red Sox", "BOS"),
    ("18966", "MLS", "LAFC", "LAFC"),
    ("187", "MLS", "LA Galaxy", "LA"),
    ("83", "LA_LIGA", "Barcelona", "BAR"),
    ("86", "LA_LIGA", "Real Madrid", "RMA"),
    ("359", "PREMIER_LEAGUE", "Arsenal", "ARS"),
    ("364", "PREMIER_LEAGUE", "Liverpool", "LIV"),
    ("203", "WORLD_CUP", "Mexico", "MEX"),
    ("660", "WORLD_CUP", "United States", "USA"),
]


def seed_test_teams(db) -> None:
    db.add_all(
        [
            Team(external_team_id=external_team_id, league=league, name=name, abbreviation=abbreviation)
            for external_team_id, league, name, abbreviation in TEST_TEAM_SEEDS
        ]
    )


@pytest.fixture(autouse=True)
def reset_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    seed_test_teams(db)
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
