import pytest

from app.db.session import SessionLocal
from app.services.seed import ensure_seeded_teams


@pytest.fixture(autouse=True)
def seed_teams(reset_db):
    with SessionLocal() as db:
        ensure_seeded_teams(db)


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db
