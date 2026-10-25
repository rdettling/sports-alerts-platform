"""Replace inning thresholds with selected regulation innings."""

from alembic import op
import sqlalchemy as sa

revision = "0005_inning_selection"
down_revision = "0004_period_selection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("user_alert_preferences", "user_game_alert_overrides"):
        op.execute(sa.text(f"""
            UPDATE {table}
            SET periods_override = CASE
                WHEN inning_start_threshold_override BETWEEN 1 AND 9
                THEN json_array(inning_start_threshold_override)
                ELSE '[]'
            END
            WHERE alert_type = 'inning_start' AND inning_start_threshold_override IS NOT NULL
        """))
        op.drop_column(table, "inning_start_threshold_override")


def downgrade() -> None:
    for table in ("user_game_alert_overrides", "user_alert_preferences"):
        op.add_column(table, sa.Column("inning_start_threshold_override", sa.Integer(), nullable=True))
        op.execute(sa.text(f"""
            UPDATE {table}
            SET inning_start_threshold_override = json_extract(periods_override, '$[0]')
            WHERE alert_type = 'inning_start' AND periods_override IS NOT NULL
        """))
