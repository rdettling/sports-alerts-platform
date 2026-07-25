import os
import subprocess

import pytest


@pytest.mark.integration
def test_alembic_upgrade_head_smoke():
    database_url = os.getenv("DATABASE_URL", "")
    if "postgresql" not in database_url:
        pytest.skip("Postgres DATABASE_URL not configured for integration smoke test")

    for command in (
        ["alembic", "upgrade", "head"],
        ["alembic", "downgrade", "0002_add_web_push"],
        ["alembic", "upgrade", "head"],
    ):
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
