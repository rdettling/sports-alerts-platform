"""store sparse alert preference overrides

Revision ID: 0004_sparse_alert_preferences
Revises: 0003_add_email_login_codes
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_sparse_alert_preferences"
down_revision: Union[str, None] = "0003_add_email_login_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUPPORTED_ALERT_TYPES = {
    "NBA": {"game_start", "close_game_late", "overtime_start", "final_result"},
    "WNBA": {"game_start", "close_game_late", "overtime_start", "final_result"},
    "NFL": {"game_start", "close_game_late", "overtime_start", "final_result"},
    "MLB": {"game_start", "inning_start", "extra_innings_start", "final_result"},
    "MLS": {"game_start", "second_half_start", "extra_time_start", "penalty_kicks", "score_changed", "final_result"},
    "WORLD_CUP": {"game_start", "second_half_start", "extra_time_start", "penalty_kicks", "score_changed", "final_result"},
}


def _defaults(league: str, alert_type: str) -> tuple[bool, int | None, int | None, int | None]:
    if alert_type not in SUPPORTED_ALERT_TYPES.get(league, set()):
        raise ValueError(f"Unsupported preference: {league}/{alert_type}")
    if alert_type == "close_game_late":
        return True, 8 if league == "NFL" else 5, 300, None
    if alert_type == "inning_start":
        return True, None, None, 7
    return True, None, None, None


def _preference_table() -> sa.TableClause:
    return sa.table(
        "user_alert_preferences",
        sa.column("id", sa.Integer),
        sa.column("league", sa.String),
        sa.column("alert_type", sa.String),
        sa.column("is_enabled_override", sa.Boolean),
        sa.column("close_game_margin_threshold_override", sa.Integer),
        sa.column("close_game_time_threshold_seconds_override", sa.Integer),
        sa.column("inning_start_threshold_override", sa.Integer),
    )


def upgrade() -> None:
    op.rename_table("user_alert_defaults", "user_alert_preferences")
    op.drop_constraint(
        "uq_user_alert_defaults_user_league_type",
        "user_alert_preferences",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_user_alert_preferences_user_league_type",
        "user_alert_preferences",
        ["user_id", "league", "alert_type"],
    )
    op.alter_column("user_alert_preferences", "is_enabled", new_column_name="is_enabled_override", nullable=True)
    op.alter_column(
        "user_alert_preferences",
        "close_game_margin_threshold",
        new_column_name="close_game_margin_threshold_override",
    )
    op.alter_column(
        "user_alert_preferences",
        "close_game_time_threshold_seconds",
        new_column_name="close_game_time_threshold_seconds_override",
    )
    op.alter_column(
        "user_alert_preferences",
        "inning_start_threshold",
        new_column_name="inning_start_threshold_override",
    )

    table = _preference_table()
    connection = op.get_bind()
    for row in connection.execute(sa.select(table)).mappings():
        try:
            defaults = _defaults(row["league"], row["alert_type"])
        except ValueError:
            connection.execute(sa.delete(table).where(table.c.id == row["id"]))
            continue
        values = {
            "is_enabled_override": None if row["is_enabled_override"] == defaults[0] else row["is_enabled_override"],
            "close_game_margin_threshold_override": (
                None
                if row["close_game_margin_threshold_override"] == defaults[1]
                else row["close_game_margin_threshold_override"]
            ),
            "close_game_time_threshold_seconds_override": (
                None
                if row["close_game_time_threshold_seconds_override"] == defaults[2]
                else row["close_game_time_threshold_seconds_override"]
            ),
            "inning_start_threshold_override": (
                None
                if row["inning_start_threshold_override"] == defaults[3]
                else row["inning_start_threshold_override"]
            ),
        }
        if all(value is None for value in values.values()):
            connection.execute(sa.delete(table).where(table.c.id == row["id"]))
        else:
            connection.execute(sa.update(table).where(table.c.id == row["id"]).values(**values))


def downgrade() -> None:
    table = _preference_table()
    connection = op.get_bind()
    for row in connection.execute(sa.select(table)).mappings():
        defaults = _defaults(row["league"], row["alert_type"])
        connection.execute(
            sa.update(table)
            .where(table.c.id == row["id"])
            .values(
                is_enabled_override=(
                    row["is_enabled_override"] if row["is_enabled_override"] is not None else defaults[0]
                ),
                close_game_margin_threshold_override=(
                    row["close_game_margin_threshold_override"]
                    if row["close_game_margin_threshold_override"] is not None
                    else defaults[1]
                ),
                close_game_time_threshold_seconds_override=(
                    row["close_game_time_threshold_seconds_override"]
                    if row["close_game_time_threshold_seconds_override"] is not None
                    else defaults[2]
                ),
                inning_start_threshold_override=(
                    row["inning_start_threshold_override"]
                    if row["inning_start_threshold_override"] is not None
                    else defaults[3]
                ),
            )
        )

    op.alter_column("user_alert_preferences", "is_enabled_override", nullable=False)
    op.alter_column("user_alert_preferences", "is_enabled_override", new_column_name="is_enabled")
    op.alter_column(
        "user_alert_preferences",
        "close_game_margin_threshold_override",
        new_column_name="close_game_margin_threshold",
    )
    op.alter_column(
        "user_alert_preferences",
        "close_game_time_threshold_seconds_override",
        new_column_name="close_game_time_threshold_seconds",
    )
    op.alter_column(
        "user_alert_preferences",
        "inning_start_threshold_override",
        new_column_name="inning_start_threshold",
    )
    op.drop_constraint(
        "uq_user_alert_preferences_user_league_type",
        "user_alert_preferences",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_user_alert_defaults_user_league_type",
        "user_alert_preferences",
        ["user_id", "league", "alert_type"],
    )
    op.rename_table("user_alert_preferences", "user_alert_defaults")
