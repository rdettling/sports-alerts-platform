"""worker sync model cleanup

Revision ID: 0007_worker_sync_model_cleanup
Revises: 0006_ingest_state_events
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_worker_sync_model_cleanup"
down_revision: Union[str, None] = "0006_ingest_state_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM worker_jobs
            WHERE job_type NOT IN ('catalog_sync', 'live_sync', 'delivery', 'cleanup_games')
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO worker_jobs (job_type, status, next_run_at, attempt_count, max_attempts)
            SELECT 'catalog_sync', 'queued', NOW(), 0, 5
            WHERE NOT EXISTS (SELECT 1 FROM worker_jobs WHERE job_type = 'catalog_sync')
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO worker_jobs (job_type, status, next_run_at, attempt_count, max_attempts)
            SELECT 'live_sync', 'queued', NOW(), 0, 5
            WHERE NOT EXISTS (SELECT 1 FROM worker_jobs WHERE job_type = 'live_sync')
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO worker_jobs (job_type, status, next_run_at, attempt_count, max_attempts)
            SELECT 'delivery', 'queued', NOW(), 0, 5
            WHERE NOT EXISTS (SELECT 1 FROM worker_jobs WHERE job_type = 'delivery')
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO worker_jobs (job_type, status, next_run_at, attempt_count, max_attempts)
            SELECT 'cleanup_games', 'queued', NOW(), 0, 5
            WHERE NOT EXISTS (SELECT 1 FROM worker_jobs WHERE job_type = 'cleanup_games')
            """
        )
    )

    op.drop_index("ix_ingest_events_occurred_at", table_name="ingest_events")
    op.drop_index("ix_ingest_events_event_type", table_name="ingest_events")
    op.drop_index("ix_ingest_events_source_key", table_name="ingest_events")
    op.drop_table("ingest_events")

    op.drop_index("ix_ingest_state_next_due", table_name="ingest_state")
    op.drop_index("ix_ingest_state_source_key", table_name="ingest_state")
    op.drop_constraint("uq_ingest_state_source_key", "ingest_state", type_="unique")
    op.drop_table("ingest_state")


def downgrade() -> None:
    op.create_table(
        "ingest_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="idle"),
        sa.Column("last_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_ingest_state_source_key", "ingest_state", ["source_key"])
    op.create_index("ix_ingest_state_source_key", "ingest_state", ["source_key"])
    op.create_index("ix_ingest_state_next_due", "ingest_state", ["next_due_at"])

    op.create_table(
        "ingest_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ingest_events_source_key", "ingest_events", ["source_key"])
    op.create_index("ix_ingest_events_event_type", "ingest_events", ["event_type"])
    op.create_index("ix_ingest_events_occurred_at", "ingest_events", ["occurred_at"])
