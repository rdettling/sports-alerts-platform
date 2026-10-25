"""Add selected quarters to league preferences and game overrides."""

from alembic import op
import sqlalchemy as sa

revision = "0003_quarter_selection"
down_revision = "0002_league_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("user_alert_preferences", "user_game_alert_overrides"):
        op.add_column(table, sa.Column("quarters_override", sa.JSON(none_as_null=True), nullable=True))


def downgrade() -> None:
    for table in ("user_game_alert_overrides", "user_alert_preferences"):
        op.drop_column(table, "quarters_override")
