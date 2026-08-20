import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

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


def test_fresh_baseline_matches_current_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"

    _alembic(database_url, "upgrade", "head")

    inspector = inspect(create_engine(database_url))
    assert set(inspector.get_table_names()) == {*Base.metadata.tables, "alembic_version"}
    for table in Base.metadata.sorted_tables:
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        assert actual_columns == set(table.columns.keys())

    _alembic(database_url, "downgrade", "base")
    assert inspect(create_engine(database_url)).get_table_names() == ["alembic_version"]
