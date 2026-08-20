import os
from pathlib import Path

import pytest
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

from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.services.seed import ensure_seeded_teams  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ensure_seeded_teams(db)
    db.close()
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
