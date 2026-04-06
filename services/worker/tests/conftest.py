import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = Path(__file__).parent / "worker_test.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB_PATH}"

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
