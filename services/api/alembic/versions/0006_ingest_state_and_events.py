"""ingest state and sparse events

Revision ID: 0006_ingest_state_events
Revises: 0005_worker_scheduler_jobs
Create Date: 2026-05-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_ingest_state_events"
down_revision: Union[str, None] = "0005_worker_scheduler_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.drop_index("ix_api_call_events_occurred_at", table_name="api_call_events")
    op.drop_index("ix_api_call_events_ingest_run_id", table_name="api_call_events")
    op.drop_index("ix_api_call_events_attempt_status", table_name="api_call_events")
    op.drop_index("ix_api_call_events_endpoint_key", table_name="api_call_events")
    op.drop_index("ix_api_call_events_provider", table_name="api_call_events")
    op.drop_index("ix_api_call_events_service", table_name="api_call_events")
    op.drop_table("api_call_events")

    op.drop_column("ingest_runs", "poll_mode")
    op.drop_column("ingest_runs", "actual_odds_calls")
    op.drop_column("ingest_runs", "actual_espn_calls")
    op.drop_column("ingest_runs", "expected_odds_calls")
    op.drop_column("ingest_runs", "expected_espn_calls")
    op.drop_table("ingest_runs")


def downgrade() -> None:
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("games_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("games_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected_espn_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected_odds_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_espn_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_odds_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("poll_mode", sa.String(length=16), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_table(
        "api_call_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("endpoint_key", sa.String(length=64), nullable=False),
        sa.Column("attempt_status", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("ingest_run_id", sa.Integer(), sa.ForeignKey("ingest_runs.id"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_api_call_events_service", "api_call_events", ["service"])
    op.create_index("ix_api_call_events_provider", "api_call_events", ["provider"])
    op.create_index("ix_api_call_events_endpoint_key", "api_call_events", ["endpoint_key"])
    op.create_index("ix_api_call_events_attempt_status", "api_call_events", ["attempt_status"])
    op.create_index("ix_api_call_events_ingest_run_id", "api_call_events", ["ingest_run_id"])
    op.create_index("ix_api_call_events_occurred_at", "api_call_events", ["occurred_at"])

    op.drop_index("ix_ingest_events_occurred_at", table_name="ingest_events")
    op.drop_index("ix_ingest_events_event_type", table_name="ingest_events")
    op.drop_index("ix_ingest_events_source_key", table_name="ingest_events")
    op.drop_table("ingest_events")

    op.drop_index("ix_ingest_state_next_due", table_name="ingest_state")
    op.drop_index("ix_ingest_state_source_key", table_name="ingest_state")
    op.drop_constraint("uq_ingest_state_source_key", "ingest_state", type_="unique")
    op.drop_table("ingest_state")
