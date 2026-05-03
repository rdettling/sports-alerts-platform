"""worker scheduler jobs and hot indexes

Revision ID: 0005_worker_scheduler_jobs
Revises: 0004_ops_telemetry
Create Date: 2026-05-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_worker_scheduler_jobs"
down_revision: Union[str, None] = "0004_ops_telemetry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_unique_constraint("uq_worker_jobs_job_type", "worker_jobs", ["job_type"])
    op.create_index("ix_worker_jobs_job_type", "worker_jobs", ["job_type"])
    op.create_index("ix_worker_jobs_status", "worker_jobs", ["status"])
    op.create_index("ix_worker_jobs_next_run_at", "worker_jobs", ["next_run_at"])
    op.create_index("ix_worker_jobs_backoff_until", "worker_jobs", ["backoff_until"])
    op.create_index("ix_worker_jobs_status_next_run", "worker_jobs", ["status", "next_run_at"])

    op.create_index("ix_sent_alerts_delivery_status_sent_at", "sent_alerts", ["delivery_status", "sent_at"])
    op.create_index("ix_games_league_is_final_status_sched", "games", ["league", "is_final", "status", "scheduled_start_time"])


def downgrade() -> None:
    op.drop_index("ix_games_league_is_final_status_sched", table_name="games")
    op.drop_index("ix_sent_alerts_delivery_status_sent_at", table_name="sent_alerts")

    op.drop_index("ix_worker_jobs_status_next_run", table_name="worker_jobs")
    op.drop_index("ix_worker_jobs_backoff_until", table_name="worker_jobs")
    op.drop_index("ix_worker_jobs_next_run_at", table_name="worker_jobs")
    op.drop_index("ix_worker_jobs_status", table_name="worker_jobs")
    op.drop_index("ix_worker_jobs_job_type", table_name="worker_jobs")
    op.drop_constraint("uq_worker_jobs_job_type", "worker_jobs", type_="unique")
    op.drop_table("worker_jobs")
