import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.db.models import Base
from app.services.seed import COMPETITION_TEAM_IDS, TEAM_CATALOG


def _run(database_url: str, *command: str) -> None:
    completed = subprocess.run(
        command,
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": "reset-test-secret",
            "WEB_BASE_URL": "http://localhost:5173",
            "CORS_ALLOW_ORIGINS": "http://localhost:5173",
            "BOOTSTRAP_ADMIN_EMAIL": "reset-admin@example.com",
        },
    )
    assert completed.returncode == 0, completed.stderr


def test_complete_reset_replaces_old_postgres_revision_and_data():
    database_url = os.getenv("POSTGRES_RESET_TEST_DATABASE_URL", "")
    if not database_url:
        pytest.skip("POSTGRES_RESET_TEST_DATABASE_URL not configured")

    url = make_url(database_url)
    assert url.get_backend_name() == "postgresql"
    assert url.host in {"127.0.0.1", "localhost"}
    assert url.database and "reset_test" in url.database

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    executable = str(Path(sys.executable).with_name("alembic"))
    _run(database_url, executable, "upgrade", "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (email, role, email_alerts_enabled) "
                "VALUES ('old-user@example.com', 'user', true)"
            )
        )
        connection.execute(text("CREATE TABLE legacy_marker (id integer primary key)"))
        connection.execute(
            text("UPDATE alembic_version SET version_num = '0008_remove_test_games'")
        )

    _run(database_url, sys.executable, "scripts/reset_database.py", "--yes")

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {*Base.metadata.tables, "alembic_version"}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_baseline"
        assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 1
        assert connection.scalar(
            text("SELECT COUNT(*) FROM users WHERE email = 'reset-admin@example.com' AND role = 'admin'")
        ) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM teams")) == len(TEAM_CATALOG)
        assert connection.scalar(text("SELECT COUNT(*) FROM competition_teams")) == sum(
            len(team_ids) for team_ids in COMPETITION_TEAM_IDS.values()
        )
