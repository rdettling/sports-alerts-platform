"""Consistent SQLite snapshots, including writes still in the WAL."""

import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.db.session import database_path


def backup_database(destination: Path) -> None:
    if destination.resolve() == database_path or destination.exists():
        raise FileExistsError(f"Backup destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".db")
    os.close(descriptor)
    try:
        with closing(
            sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
        ) as source:
            with closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite backup integrity check failed")
        os.link(temporary, destination)
    finally:
        os.unlink(temporary)


def create_daily_backup() -> None:
    directory = database_path.parent / "backups"
    destination = directory / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".db")
    if destination.exists():
        return
    backup_database(destination)
    for old_backup in sorted(directory.glob("????-??-??.db"))[:-7]:
        old_backup.unlink()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Back up the running SQLite database safely."
    )
    parser.add_argument("destination", type=Path)
    backup_database(parser.parse_args().destination)
