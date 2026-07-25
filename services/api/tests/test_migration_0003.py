import importlib.util
from pathlib import Path


def test_email_login_code_migration_only_clears_login_tokens(monkeypatch):
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0003_add_email_login_codes.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0003", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    executed: list[str] = []
    added_columns: list[tuple[str, str]] = []
    monkeypatch.setattr(migration.op, "execute", executed.append)
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added_columns.append((table, column.name)),
    )

    migration.upgrade()

    assert executed == ["DELETE FROM email_login_tokens"]
    assert added_columns == [
        ("email_login_tokens", "code_hash"),
        ("email_login_tokens", "failed_code_attempts"),
    ]
