"""Share selected regulation periods across quarter- and period-start alerts."""

from alembic import op
import sqlalchemy as sa

revision = "0004_period_selection"
down_revision = "0003_quarter_selection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("user_alert_preferences", "user_game_alert_overrides"):
        op.alter_column(table, "quarters_override", new_column_name="periods_override", existing_type=sa.JSON())


def downgrade() -> None:
    for table in ("user_game_alert_overrides", "user_alert_preferences"):
        op.alter_column(table, "periods_override", new_column_name="quarters_override", existing_type=sa.JSON())
