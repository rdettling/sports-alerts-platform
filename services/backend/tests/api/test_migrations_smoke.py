import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db.models import Base


def _alembic(database_url: str, *args: str) -> None:
    completed = subprocess.run(
        [str(Path(sys.executable).with_name("alembic")), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DATABASE_URL": database_url},
    )
    assert completed.returncode == 0, completed.stderr


def test_migration_revision_ids_fit_alembic_version_column():
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    revisions = ScriptDirectory.from_config(config).walk_revisions()

    assert [revision.revision for revision in revisions if len(revision.revision) > 32] == []


def test_fresh_baseline_matches_current_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"

    _alembic(database_url, "upgrade", "head")

    inspector = inspect(create_engine(database_url))
    assert set(inspector.get_table_names()) == {*Base.metadata.tables, "alembic_version"}
    for table in Base.metadata.sorted_tables:
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        assert actual_columns == set(table.columns.keys())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert "email_alerts_enabled" in user_columns
    assert "alert_delivery_mode" not in user_columns
    odds_outcome_columns = {
        column["name"]: column for column in inspector.get_columns("game_odds_outcomes_current")
    }
    assert odds_outcome_columns["outcome_key"]["type"].length == 128

    _alembic(database_url, "downgrade", "base")
    assert inspect(create_engine(database_url)).get_table_names() == ["alembic_version"]


def test_latest_migration_removes_recreated_retired_setting(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'retired-setting.db'}"
    engine = create_engine(database_url)
    _alembic(database_url, "upgrade", "0008_remove_retired_competition")

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO competition_settings "
                "(competition, is_enabled, created_at, updated_at) "
                "VALUES ('WORLD_CUP', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    _alembic(database_url, "upgrade", "head")

    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT COUNT(*) FROM competition_settings WHERE competition = 'WORLD_CUP'")
        ) == 0
