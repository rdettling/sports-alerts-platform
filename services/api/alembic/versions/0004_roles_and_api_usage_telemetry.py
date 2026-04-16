"""roles and api usage telemetry

Revision ID: 0004_ops_telemetry
Revises: 0003_email_magic_link_auth
Create Date: 2026-04-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_ops_telemetry"
down_revision: Union[str, None] = "0003_email_magic_link_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    role_enum = sa.Enum("user", "admin", name="user_role")
    role_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column("role", role_enum, nullable=False, server_default="user"),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.add_column("ingest_runs", sa.Column("expected_espn_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingest_runs", sa.Column("expected_odds_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingest_runs", sa.Column("actual_espn_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingest_runs", sa.Column("actual_odds_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingest_runs", sa.Column("poll_mode", sa.String(length=16), nullable=True))

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

    op.create_table(
        "api_call_rollups_hourly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("endpoint_key", sa.String(length=64), nullable=False),
        sa.Column("attempt_status", sa.String(length=32), nullable=False),
        sa.Column("call_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint(
        "uq_api_call_rollups_hourly_bucket_dims",
        "api_call_rollups_hourly",
        ["bucket_start", "service", "provider", "endpoint_key", "attempt_status"],
    )
    op.create_index("ix_api_call_rollups_hourly_bucket_start", "api_call_rollups_hourly", ["bucket_start"])
    op.create_index("ix_api_call_rollups_hourly_service", "api_call_rollups_hourly", ["service"])
    op.create_index("ix_api_call_rollups_hourly_provider", "api_call_rollups_hourly", ["provider"])
    op.create_index("ix_api_call_rollups_hourly_endpoint_key", "api_call_rollups_hourly", ["endpoint_key"])
    op.create_index("ix_api_call_rollups_hourly_attempt_status", "api_call_rollups_hourly", ["attempt_status"])


def downgrade() -> None:
    op.drop_index("ix_api_call_rollups_hourly_attempt_status", table_name="api_call_rollups_hourly")
    op.drop_index("ix_api_call_rollups_hourly_endpoint_key", table_name="api_call_rollups_hourly")
    op.drop_index("ix_api_call_rollups_hourly_provider", table_name="api_call_rollups_hourly")
    op.drop_index("ix_api_call_rollups_hourly_service", table_name="api_call_rollups_hourly")
    op.drop_index("ix_api_call_rollups_hourly_bucket_start", table_name="api_call_rollups_hourly")
    op.drop_constraint("uq_api_call_rollups_hourly_bucket_dims", "api_call_rollups_hourly", type_="unique")
    op.drop_table("api_call_rollups_hourly")

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

    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")

    role_enum = sa.Enum("user", "admin", name="user_role")
    role_enum.drop(op.get_bind(), checkfirst=True)
