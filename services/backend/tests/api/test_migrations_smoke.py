import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


def _alembic(database_url: str, *args: str) -> None:
    completed = subprocess.run(
        [str(Path(sys.executable).with_name("alembic")), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DATABASE_URL": database_url},
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.integration
def test_sparse_alert_preference_migration_cycle():
    database_url = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not database_url:
        pytest.skip("MIGRATION_TEST_DATABASE_URL not configured for integration smoke test")

    _alembic(database_url, "upgrade", "0003_add_email_login_codes")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        existing_user_id = connection.scalar(
            text("SELECT id FROM users WHERE email = 'migration-preferences@example.com'")
        )
        if existing_user_id is not None:
            connection.execute(
                text("DELETE FROM user_alert_defaults WHERE user_id = :user_id"),
                {"user_id": existing_user_id},
            )
            connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": existing_user_id})
        user_id = connection.scalar(
            text(
                "INSERT INTO users (email, role, alert_delivery_mode) "
                "VALUES ('migration-preferences@example.com', 'user', 'email') RETURNING id"
            )
        )
        connection.execute(
            text(
                "INSERT INTO user_alert_defaults "
                "(user_id, league, alert_type, is_enabled, close_game_margin_threshold, "
                "close_game_time_threshold_seconds, inning_start_threshold) VALUES "
                "(:user_id, 'NBA', 'game_start', true, NULL, NULL, NULL), "
                "(:user_id, 'NBA', 'close_game_late', true, 3, 90, NULL), "
                "(:user_id, 'NBA', 'score_changed', true, NULL, NULL, NULL)"
            ),
            {"user_id": user_id},
        )

    _alembic(database_url, "upgrade", "head")
    assert "user_alert_preferences" in inspect(engine).get_table_names()
    assert "user_alert_defaults" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT alert_type, is_enabled_override, close_game_margin_threshold_override, "
                "close_game_time_threshold_seconds_override FROM user_alert_preferences "
                "WHERE user_id = :user_id"
            ),
            {"user_id": user_id},
        ).mappings().all()
    assert rows == [
        {
            "alert_type": "close_game_late",
            "is_enabled_override": None,
            "close_game_margin_threshold_override": 3,
            "close_game_time_threshold_seconds_override": 90,
        }
    ]

    _alembic(database_url, "downgrade", "0003_add_email_login_codes")
    assert "user_alert_defaults" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT alert_type, is_enabled, close_game_margin_threshold, "
                "close_game_time_threshold_seconds FROM user_alert_defaults WHERE user_id = :user_id"
            ),
            {"user_id": user_id},
        ).mappings().one()
    assert row == {
        "alert_type": "close_game_late",
        "is_enabled": True,
        "close_game_margin_threshold": 3,
        "close_game_time_threshold_seconds": 90,
    }

    _alembic(database_url, "upgrade", "head")
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM user_alert_preferences WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
