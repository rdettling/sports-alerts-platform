import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import CompetitionSetting, OddsApiDailyUsage, UserTeamFollow
from app.db.session import engine


def test_sqlite_enforces_foreign_keys_and_uses_wal():
    with engine.connect() as db:
        assert db.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert db.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        with pytest.raises(IntegrityError):
            db.execute(insert(UserTeamFollow).values(user_id=999, team_id=999))


def test_reader_is_not_blocked_by_uncommitted_writer():
    with engine.begin() as db:
        db.execute(
            insert(CompetitionSetting).values(competition="NBA", is_enabled=True)
        )
    with engine.begin() as writer:
        writer.execute(update(CompetitionSetting).values(is_enabled=False))

        def read():
            with engine.connect() as reader:
                return reader.scalar(select(CompetitionSetting.is_enabled))

        with ThreadPoolExecutor(max_workers=1) as threads:
            assert threads.submit(read).result(timeout=2) is True
    with engine.connect() as db:
        assert db.scalar(select(CompetitionSetting.is_enabled)) is False


def test_concurrent_writes_complete_without_losing_updates():
    from datetime import date

    today = date.today()
    with engine.begin() as db:
        db.execute(insert(OddsApiDailyUsage).values(usage_date=today, credits_used=0))

    def write(_):
        with engine.begin() as db:
            db.execute(
                update(OddsApiDailyUsage).values(
                    credits_used=OddsApiDailyUsage.credits_used + 1
                )
            )

    with ThreadPoolExecutor(max_workers=4) as threads:
        list(threads.map(write, range(20)))
    with engine.connect() as db:
        assert db.scalar(select(OddsApiDailyUsage.credits_used)) == 20


def test_backup_includes_committed_wal_data_and_refuses_overwrite(
    tmp_path, monkeypatch
):
    from app.db import backup

    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    monkeypatch.setattr(backup, "database_path", source)
    with closing(sqlite3.connect(source)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE marker (value TEXT)")
        db.execute("INSERT INTO marker VALUES ('saved')")
        db.commit()
        backup.backup_database(destination)
    with closing(sqlite3.connect(destination)) as restored:
        assert restored.execute("SELECT value FROM marker").fetchone() == ("saved",)
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    with pytest.raises(FileExistsError):
        backup.backup_database(destination)
    with pytest.raises(FileExistsError):
        backup.backup_database(source)


def test_daily_backup_keeps_seven_snapshots(tmp_path, monkeypatch):
    from app.db import backup

    source = tmp_path / "source.db"
    monkeypatch.setattr(backup, "database_path", source)
    with closing(sqlite3.connect(source)) as db:
        db.execute("CREATE TABLE marker (id INTEGER)")
    directory = tmp_path / "backups"
    directory.mkdir()
    for day in range(1, 9):
        (directory / f"2000-01-{day:02d}.db").touch()
    backup.create_daily_backup()
    assert len(list(directory.glob("*.db"))) == 7
    assert not (directory / "2000-01-01.db").exists()
    backup.create_daily_backup()
    assert len(list(directory.glob("*.db"))) == 7


@pytest.mark.parametrize("offset_hours", [0, -7, 5.5])
def test_sqlite_datetime_round_trip_normalizes_offsets_to_utc(offset_hours):
    from datetime import datetime, timedelta, timezone
    from app.db.models import EmailLoginToken

    local_time = datetime(2026, 10, 24, 16, 0, tzinfo=timezone(timedelta(hours=offset_hours)))
    with engine.begin() as db:
        db.execute(insert(EmailLoginToken).values(email="timezone@example.com", token_hash="a" * 64, code_hash="b" * 64, expires_at=local_time))
    with engine.connect() as db:
        expires_at = db.scalar(select(EmailLoginToken.expires_at))
        assert expires_at == local_time.astimezone(timezone.utc)
        assert expires_at.tzinfo == timezone.utc
        assert db.scalar(select(EmailLoginToken.created_at)).tzinfo == timezone.utc
        assert db.scalar(select(EmailLoginToken.consumed_at)) is None


def test_existing_sqlite_timestamps_are_loaded_as_utc():
    from datetime import datetime, timezone
    from app.db.models import EmailLoginToken

    with engine.begin() as db:
        db.exec_driver_sql("INSERT INTO email_login_tokens (email, token_hash, code_hash, expires_at) VALUES ('existing@example.com', 'token', 'code', '2026-10-24 23:00:00')")
    with engine.connect() as db:
        assert db.scalar(select(EmailLoginToken.expires_at)) == datetime(2026, 10, 24, 23, tzinfo=timezone.utc)
