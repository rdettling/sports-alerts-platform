from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.seed import ensure_seeded_teams  # noqa: E402

SPORTS_TABLES = [
    "sent_alerts",
    "user_game_alert_overrides",
    "user_game_unfollows",
    "user_game_follows",
    "user_team_follows",
    "user_alert_defaults",
    "game_odds_current",
    "games",
    "teams",
    "league_settings",
    "worker_jobs",
    "ingest_events",
    "ingest_state",
    "api_call_rollups_hourly",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset sports-domain data and reseed teams.")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive reset")
    args = parser.parse_args()

    if not args.yes:
        print("Refusing to run without --yes")
        return 2

    db = SessionLocal()
    try:
        existing_tables = set(inspect(db.get_bind()).get_table_names())
        for table in SPORTS_TABLES:
            if table not in existing_tables:
                print(f"Skipping missing table: {table}")
                continue
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
        ensure_seeded_teams(db)
    finally:
        db.close()

    print("Sports-domain reset complete. Team seeds restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
