from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.services.seed import ensure_bootstrap_admin, ensure_seeded_teams  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete every database table, rebuild the baseline, and reseed catalogs."
    )
    parser.add_argument("--yes", action="store_true", help="Confirm the destructive reset")
    args = parser.parse_args()

    if not args.yes:
        print("Refusing to run without --yes")
        return 2

    existing = MetaData()
    existing.reflect(bind=engine)
    existing.drop_all(bind=engine)

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")

    with SessionLocal() as db:
        ensure_seeded_teams(db)
        ensure_bootstrap_admin(db, settings.bootstrap_admin_email)

    print("Database reset complete. Baseline schema and catalogs restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
