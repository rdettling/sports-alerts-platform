"""remove persisted worker jobs

Revision ID: 0005_remove_worker_jobs
Revises: 0004_sparse_alert_preferences
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005_remove_worker_jobs"
down_revision: Union[str, None] = "0004_sparse_alert_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("worker_jobs")


def downgrade() -> None:
    pass
