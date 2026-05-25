"""add league dimension to worker jobs

Revision ID: 0008_worker_jobs_league_dim
Revises: 0007_worker_sync_model_cleanup
Create Date: 2026-05-25 15:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_worker_jobs_league_dim"
down_revision = "0007_worker_sync_model_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("worker_jobs", sa.Column("league", sa.String(length=16), nullable=True))
    op.drop_constraint("uq_worker_jobs_job_type", "worker_jobs", type_="unique")
    op.create_unique_constraint("uq_worker_jobs_job_type_league", "worker_jobs", ["job_type", "league"])
    op.create_index("ix_worker_jobs_league", "worker_jobs", ["league"])

    op.execute(
        """
        UPDATE worker_jobs
        SET league = 'NBA'
        WHERE job_type IN ('catalog_sync', 'live_sync')
        """
    )

    op.execute(
        """
        INSERT INTO worker_jobs (job_type, league, status, next_run_at, attempt_count, max_attempts)
        SELECT 'catalog_sync', 'MLB', 'queued', NOW(), 0, 5
        WHERE NOT EXISTS (
          SELECT 1 FROM worker_jobs WHERE job_type = 'catalog_sync' AND league = 'MLB'
        )
        """
    )
    op.execute(
        """
        INSERT INTO worker_jobs (job_type, league, status, next_run_at, attempt_count, max_attempts)
        SELECT 'live_sync', 'MLB', 'queued', NOW(), 0, 5
        WHERE NOT EXISTS (
          SELECT 1 FROM worker_jobs WHERE job_type = 'live_sync' AND league = 'MLB'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM worker_jobs
        WHERE job_type IN ('catalog_sync', 'live_sync')
          AND league = 'MLB'
        """
    )
    op.drop_index("ix_worker_jobs_league", table_name="worker_jobs")
    op.drop_constraint("uq_worker_jobs_job_type_league", "worker_jobs", type_="unique")
    op.create_unique_constraint("uq_worker_jobs_job_type", "worker_jobs", ["job_type"])
    op.drop_column("worker_jobs", "league")
