"""add user game unfollows for team-follow game overrides

Revision ID: 0009_user_game_unfollows
Revises: 0008_worker_jobs_league_dim
Create Date: 2026-05-25 22:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_user_game_unfollows"
down_revision = "0008_worker_jobs_league_dim"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_game_unfollows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "game_id", name="uq_user_game_unfollows_user_game"),
    )
    op.create_index(op.f("ix_user_game_unfollows_id"), "user_game_unfollows", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_game_unfollows_id"), table_name="user_game_unfollows")
    op.drop_table("user_game_unfollows")
