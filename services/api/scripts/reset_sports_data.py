from __future__ import annotations

import argparse
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.seed import seed_teams_if_empty

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
        for table in SPORTS_TABLES:
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
        seed_teams_if_empty(db)
    finally:
        db.close()

    print("Sports-domain reset complete. Team seeds restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
