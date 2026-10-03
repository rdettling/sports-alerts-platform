"""Remove the stale retired competition setting.

Revision ID: 0009_remove_stale_competition_setting
Revises: 0008_remove_retired_competition
Create Date: 2026-10-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0009_remove_stale_competition_setting"
down_revision: Union[str, None] = "0008_remove_retired_competition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM competition_settings WHERE competition = 'WORLD_CUP'")


def downgrade() -> None:
    pass
