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
        db.execute(text(
            "INSERT INTO user_game_alert_overrides (user_id, game_id, alert_type, close_game_margin_threshold_override) "
            "VALUES (:user, :game, 'close_game_late', 2)"
        ), {"user": user.id, "game": game.id})
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
    _alembic(database_url, "upgrade", "0002_league_preferences")
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


def test_quarter_migration_preserves_existing_enabled_preferences(tmp_path):
    from sqlalchemy import text
    from app.db.models import User, UserAlertPreference
    from app.services.alert_preferences import resolve_alert_settings

    database_url = f"sqlite:///{tmp_path / 'quarter-migration.db'}"
    _alembic(database_url, "upgrade", "0002_league_preferences")
    engine = create_engine(database_url)
    with Session(engine) as db:
        db.add(User(id=1, email="periods@example.com"))
        db.commit()
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO user_alert_preferences (user_id, competition, alert_type, is_enabled_override) "
            "VALUES (1, 'NBA', 'quarter_start', 1)"
        ))
    _alembic(database_url, "upgrade", "head")
    with Session(engine) as db:
        preference = db.scalar(select(UserAlertPreference))
        settings = resolve_alert_settings("NBA", "quarter_start", preference)
        assert settings.is_enabled is True
        assert settings.periods == [2, 3, 4]
        preference.periods_override = [2, 4]
        db.commit()
        db.expire_all()
        assert resolve_alert_settings("NBA", "quarter_start", db.scalar(select(UserAlertPreference))).periods == [2, 4]
    _alembic(database_url, "downgrade", "0002_league_preferences")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT is_enabled_override FROM user_alert_preferences")).scalar() == 1
    engine.dispose()



def test_shared_period_migration_preserves_quarter_selection(tmp_path):
    from sqlalchemy import text
    from app.db.models import User, UserAlertPreference

    database_url = f"sqlite:///{tmp_path / 'shared-periods.db'}"
    _alembic(database_url, "upgrade", "0003_quarter_selection")
    engine = create_engine(database_url)
    with Session(engine) as db:
        db.add(User(id=1, email="selection@example.com"))
        db.commit()
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO user_alert_preferences (user_id, competition, alert_type, is_enabled_override, quarters_override) "
            "VALUES (1, 'NBA', 'quarter_start', 1, '[2, 4]')"
        ))
    _alembic(database_url, "upgrade", "head")
    with Session(engine) as db:
        preference = db.scalar(select(UserAlertPreference))
        assert preference.is_enabled_override is True
        assert preference.periods_override == [2, 4]
    _alembic(database_url, "downgrade", "0003_quarter_selection")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT quarters_override FROM user_alert_preferences")).scalar() == "[2, 4]"
    engine.dispose()


def test_inning_migration_preserves_preferences_and_game_overrides(tmp_path):
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.db.models import Game, Team, User, UserAlertPreference, UserGameAlertOverride
    from app.services.seed import ensure_seeded_teams

    database_url = f"sqlite:///{tmp_path / 'inning-selection.db'}"
    _alembic(database_url, "upgrade", "0004_period_selection")
    engine = create_engine(database_url)
    with Session(engine) as db:
        ensure_seeded_teams(db)
        teams = db.scalars(select(Team).order_by(Team.id).limit(2)).all()
        db.add(User(id=1, email="innings@example.com"))
        db.add(Game(id=1, external_game_id="inning-migration", competition="MLB",
                    home_team_id=teams[0].id, away_team_id=teams[1].id,
                    scheduled_start_time=datetime.now(timezone.utc), status="scheduled"))
        db.commit()
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO user_alert_preferences (user_id, competition, alert_type, is_enabled_override, inning_start_threshold_override) "
            "VALUES (1, 'MLB', 'inning_start', 1, 5)"
        ))
        connection.execute(text(
            "INSERT INTO user_game_alert_overrides (user_id, game_id, alert_type, inning_start_threshold_override) "
            "VALUES (1, 1, 'inning_start', 9)"
        ))
    _alembic(database_url, "upgrade", "head")
    with Session(engine) as db:
        assert db.scalar(select(UserAlertPreference)).periods_override == [5]
        assert db.scalar(select(UserGameAlertOverride)).periods_override == [9]
        assert db.get(User, 1).email == "innings@example.com"
    _alembic(database_url, "downgrade", "0004_period_selection")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT inning_start_threshold_override FROM user_alert_preferences")).scalar() == 5
        assert connection.execute(text("SELECT inning_start_threshold_override FROM user_game_alert_overrides")).scalar() == 9
    engine.dispose()


def test_redeploy_preserves_personal_data_and_referenced_identities(tmp_path):
    from datetime import datetime, timedelta, timezone

    from app.db.models import (
        Game, PushSubscription, Team, User, UserAlertPreference,
        UserGameAlertOverride, UserGameFollow, UserTeamFollow,
    )
    from app.services.competitions import competition_teams_query
    from app.services.seed import ensure_bootstrap_admin, ensure_seeded_teams

    database_url = f"sqlite:///{tmp_path / 'redeploy.db'}"
    _alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            ensure_seeded_teams(db)
            home, away = db.scalars(competition_teams_query("NBA").order_by(Team.id).limit(2)).all()
            user = User(email="preserve@example.com", email_alerts_enabled=False, hidden_competitions=["MLB"])
            game = Game(
                external_game_id="preserved-game", competition="NBA",
                home_team_id=home.id, away_team_id=away.id,
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(days=1),
            )
            db.add_all([user, game])
            db.flush()
            team_follow = UserTeamFollow(user_id=user.id, team_id=home.id)
            game_follow = UserGameFollow(user_id=user.id, game_id=game.id)
            preference = UserAlertPreference(user_id=user.id, competition="NBA", alert_type="close_game", is_enabled_override=False)
            override = UserGameAlertOverride(user_id=user.id, game_id=game.id, alert_type="close_game", is_enabled_override=True)
            subscription = PushSubscription(user_id=user.id, endpoint="https://push.example/device", p256dh="device-key", auth="device-auth")
            db.add_all([team_follow, game_follow, preference, override, subscription])
            db.commit()
            identities = [(type(row), row.id) for row in (user, home, away, game, team_follow, game_follow, preference, override, subscription)]
            home.name = "Outdated name"
            db.commit()

            _alembic(database_url, "upgrade", "head")
            ensure_seeded_teams(db)
            ensure_bootstrap_admin(db, "admin@example.com")
            db.expire_all()

            assert all(db.get(model, row_id) is not None for model, row_id in identities)
            assert user.email_alerts_enabled is False
            assert user.hidden_competitions == ["MLB"]
            assert home.name != "Outdated name"
            assert team_follow.team_id == home.id
            assert game_follow.game_id == game.id
            assert preference.is_enabled_override is False
            assert override.is_enabled_override is True
            assert (subscription.endpoint, subscription.p256dh, subscription.auth) == (
                "https://push.example/device", "device-key", "device-auth",
            )
    finally:
        engine.dispose()
