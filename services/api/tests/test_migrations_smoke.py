import os
import subprocess

import pytest


@pytest.mark.integration
def test_alembic_upgrade_head_smoke():
    database_url = os.getenv("DATABASE_URL", "")
    if "postgresql" not in database_url:
        pytest.skip("Postgres DATABASE_URL not configured for integration smoke test")

    completed = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
