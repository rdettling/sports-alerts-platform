import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db.models import Base


def _alembic(database_url: str, *args: str) -> None:
    completed = subprocess.run(
        [str(Path(sys.executable).with_name("alembic")), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DATABASE_URL": database_url},
    )
    assert completed.returncode == 0, completed.stderr


def test_migration_revision_ids_fit_alembic_version_column():
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    revisions = ScriptDirectory.from_config(config).walk_revisions()

    assert [revision.revision for revision in revisions if len(revision.revision) > 32] == []


def test_fresh_baseline_matches_current_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"

    _alembic(database_url, "upgrade", "head")

    inspector = inspect(create_engine(database_url))
    assert set(inspector.get_table_names()) == {*Base.metadata.tables, "alembic_version"}
    for table in Base.metadata.sorted_tables:
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        assert actual_columns == set(table.columns.keys())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert "email_alerts_enabled" in user_columns
    assert "alert_delivery_mode" not in user_columns
    odds_outcome_columns = {
        column["name"]: column for column in inspector.get_columns("game_odds_outcomes_current")
    }
    assert odds_outcome_columns["outcome_key"]["type"].length == 128

    from app.services.seed import ensure_seeded_teams, ensure_bootstrap_admin
    from app.db.models import Team, User
    with Session(create_engine(database_url)) as db:
        ensure_seeded_teams(db)
        ensure_bootstrap_admin(db, "fresh-admin@example.com")
        assert db.scalar(select(User.email)) == "fresh-admin@example.com"
        assert db.scalar(select(Team.id)) is not None

    _alembic(database_url, "downgrade", "base")
    assert inspect(create_engine(database_url)).get_table_names() == ["alembic_version"]


def test_league_migration_resets_only_preferences(tmp_path):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text
    from app.db.models import (
        Alert,
        AlertDelivery,
        EmailLoginToken,
        Game,
        PushSubscription,
        Team,
        User,
        UserGameAlertOverride,
        UserGameFollow,
        UserTeamFollow,
    )
    from app.services.seed import ensure_seeded_teams

    database_url = f"sqlite:///{tmp_path / 'league-migration.db'}"
    _alembic(database_url, "upgrade", "0001_sqlite")
    engine = create_engine(database_url)
    with Session(engine) as db:
        ensure_seeded_teams(db)
        user = User(
            email="preserved@example.com",
            email_alerts_enabled=False,
            hidden_competitions=["NBA"],
        )
        db.add(user)
        db.flush()
        teams = db.scalars(select(Team).order_by(Team.id).limit(2)).all()
        game = Game(
            external_game_id="preserved-game",
            competition="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc),
            status="scheduled",
        )
        db.add(game)
        db.flush()
        db.add_all(
            [
                UserTeamFollow(user_id=user.id, team_id=teams[0].id),
                UserGameFollow(user_id=user.id, game_id=game.id),
                UserGameAlertOverride(
                    user_id=user.id,
                    game_id=game.id,
                    alert_type="close_game_late",
                    close_game_margin_threshold_override=2,
                ),
                EmailLoginToken(
                    email=user.email,
                    token_hash="a" * 64,
                    code_hash="b" * 64,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                ),
                PushSubscription(
                    user_id=user.id,
                    endpoint="https://push.example.com/test",
                    p256dh="key",
                    auth="auth",
                ),
            ]
        )
        alert = Alert(
            user_id=user.id,
            game_id=game.id,
            alert_type="game_start",
            event_key="preserved-alert",
        )
        db.add(alert)
        db.flush()
        db.add(AlertDelivery(alert_id=alert.id, channel="email", status="sent"))
        db.execute(
            text(
                "INSERT INTO user_alert_preferences (user_id, sport, alert_type, is_enabled_override) VALUES (:user, 'basketball', 'game_start', 0)"
            ),
            {"user": user.id},
        )
        db.commit()

    preserved_tables = set(Base.metadata.tables) - {"user_alert_preferences"}
    with engine.connect() as connection:
        before = {
            name: connection.execute(text(f'SELECT * FROM "{name}"')).all()
            for name in preserved_tables
        }
    _alembic(database_url, "upgrade", "head")
    with engine.connect() as connection:
        for name in preserved_tables:
            assert (
                connection.execute(text(f'SELECT * FROM "{name}"')).all()
                == before[name]
            )
        assert (
            connection.execute(text("SELECT * FROM user_alert_preferences")).all() == []
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    constraints = inspect(engine).get_unique_constraints("user_alert_preferences")
    assert any(
        c["column_names"] == ["user_id", "competition", "alert_type"]
        for c in constraints
    )
    _alembic(database_url, "downgrade", "0001_sqlite")
    assert "sport" in {
        column["name"]
        for column in inspect(engine).get_columns("user_alert_preferences")
    }
    _alembic(database_url, "upgrade", "head")
    engine.dispose()
