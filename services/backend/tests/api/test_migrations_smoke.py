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
def test_current_schema_upgrade():
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
        home_team_id = connection.scalar(
            text(
                "INSERT INTO teams (external_team_id, league, name, abbreviation) "
                "VALUES ('migration-home', 'NBA', 'Migration Home', 'MH') RETURNING id"
            )
        )
        away_team_id = connection.scalar(
            text(
                "INSERT INTO teams (external_team_id, league, name, abbreviation) "
                "VALUES ('migration-away', 'NBA', 'Migration Away', 'MA') RETURNING id"
            )
        )
        game_id = connection.scalar(
            text(
                "INSERT INTO games "
                "(external_game_id, league, home_team_id, away_team_id, scheduled_start_time, "
                "status, is_final, is_test) VALUES "
                "('migration-odds-game', 'NBA', :home_team_id, :away_team_id, NOW(), "
                "'scheduled', false, false) RETURNING id"
            ),
            {"home_team_id": home_team_id, "away_team_id": away_team_id},
        )
        test_game_id = connection.scalar(
            text(
                "INSERT INTO games "
                "(external_game_id, league, home_team_id, away_team_id, scheduled_start_time, "
                "status, is_final, is_test) VALUES "
                "('migration-test-game', 'NBA', :home_team_id, :away_team_id, NOW(), "
                "'scheduled', false, true) RETURNING id"
            ),
            {"home_team_id": home_team_id, "away_team_id": away_team_id},
        )
        connection.execute(
            text("INSERT INTO user_game_follows (user_id, game_id) VALUES (:user_id, :game_id)"),
            {"user_id": user_id, "game_id": test_game_id},
        )
        connection.execute(
            text("INSERT INTO user_game_unfollows (user_id, game_id) VALUES (:user_id, :game_id)"),
            {"user_id": user_id, "game_id": test_game_id},
        )
        connection.execute(
            text(
                "INSERT INTO user_game_alert_overrides "
                "(user_id, game_id, alert_type, is_enabled_override) "
                "VALUES (:user_id, :game_id, 'game_start', false)"
            ),
            {"user_id": user_id, "game_id": test_game_id},
        )
        test_alert_id = connection.scalar(
            text(
                "INSERT INTO alerts (user_id, game_id, alert_type, event_key) "
                "VALUES (:user_id, :game_id, 'game_start', 'migration-test-alert') RETURNING id"
            ),
            {"user_id": user_id, "game_id": test_game_id},
        )
        connection.execute(
            text(
                "INSERT INTO alert_deliveries (alert_id, channel, status) "
                "VALUES (:alert_id, 'email', 'sent')"
            ),
            {"alert_id": test_alert_id},
        )
        odds_id = connection.scalar(
            text(
                "INSERT INTO game_odds_current (game_id, provider, market, fetched_at) "
                "VALUES (:game_id, 'the_odds_api', 'h2h', NOW()) RETURNING id"
            ),
            {"game_id": game_id},
        )
        connection.execute(
            text(
                "INSERT INTO game_odds_outcomes_current "
                "(odds_id, outcome_key, outcome_label, outcome_order, price_american, team_side) "
                "VALUES (:odds_id, 'migration_home', 'Migration Home', 0, -110, 'home')"
            ),
            {"odds_id": odds_id},
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
    assert "worker_jobs" not in inspect(engine).get_table_names()
    assert "api_call_rollups_hourly" not in inspect(engine).get_table_names()
    game_columns = {column["name"] for column in inspect(engine).get_columns("games")}
    assert "is_test" not in game_columns
    odds_columns = {column["name"] for column in inspect(engine).get_columns("game_odds_current")}
    assert "provider" not in odds_columns
    assert "market" not in odds_columns
    assert any(
        constraint["column_names"] == ["game_id"]
        for constraint in inspect(engine).get_unique_constraints("game_odds_current")
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM game_odds_current")) == 0
        assert connection.scalar(text("SELECT COUNT(*) FROM game_odds_outcomes_current")) == 0
        assert connection.scalar(text("SELECT COUNT(*) FROM games WHERE external_game_id = 'migration-test-game'")) == 0
        assert connection.scalar(text("SELECT COUNT(*) FROM alerts WHERE event_key = 'migration-test-alert'")) == 0
        assert connection.scalar(
            text("SELECT COUNT(*) FROM user_game_follows WHERE game_id = :game_id"),
            {"game_id": test_game_id},
        ) == 0
        assert connection.scalar(
            text("SELECT COUNT(*) FROM user_game_unfollows WHERE game_id = :game_id"),
            {"game_id": test_game_id},
        ) == 0
        assert connection.scalar(
            text("SELECT COUNT(*) FROM user_game_alert_overrides WHERE game_id = :game_id"),
            {"game_id": test_game_id},
        ) == 0
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

    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM user_alert_preferences WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        connection.execute(text("DELETE FROM games WHERE id = :game_id"), {"game_id": game_id})
        connection.execute(
            text("DELETE FROM teams WHERE id IN (:home_team_id, :away_team_id)"),
            {"home_team_id": home_team_id, "away_team_id": away_team_id},
        )
