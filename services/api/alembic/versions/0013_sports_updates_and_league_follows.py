"""sports updates feed and league follows

Revision ID: 0013_updates_feed
Revises: 0012_nba_close_game_5min
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_updates_feed"
down_revision: Union[str, None] = "0012_nba_close_game_5min"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_league_follows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("league", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "league", name="uq_user_league_follows_user_league"),
    )
    op.create_index(op.f("ix_user_league_follows_id"), "user_league_follows", ["id"], unique=False)

    op.create_table(
        "sports_update_source_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_name", sa.String(length=80), nullable=False),
        sa.Column("feed_key", sa.String(length=32), nullable=False),
        sa.Column("league", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("article_url", sa.String(length=1000), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_sports_update_source_items_dedupe_key"),
    )
    op.create_index(op.f("ix_sports_update_source_items_id"), "sports_update_source_items", ["id"], unique=False)
    op.create_index("ix_sports_update_source_items_league_published", "sports_update_source_items", ["league", "published_at"], unique=False)
    op.create_index(op.f("ix_sports_update_source_items_feed_key"), "sports_update_source_items", ["feed_key"], unique=False)

    op.create_table(
        "sports_updates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_item_id", sa.Integer(), nullable=False),
        sa.Column("league", sa.String(length=16), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=True),
        sa.Column("importance", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("classifier_status", sa.String(length=16), nullable=False),
        sa.Column("classifier_version", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_item_id"], ["sports_update_source_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_item_id", name="uq_sports_updates_source_item"),
    )
    op.create_index(op.f("ix_sports_updates_id"), "sports_updates", ["id"], unique=False)
    op.create_index("ix_sports_updates_status_created", "sports_updates", ["classifier_status", "created_at"], unique=False)
    op.create_index("ix_sports_updates_scope_league", "sports_updates", ["scope", "league"], unique=False)
    op.create_index(op.f("ix_sports_updates_classifier_status"), "sports_updates", ["classifier_status"], unique=False)
    op.create_index(op.f("ix_sports_updates_league"), "sports_updates", ["league"], unique=False)
    op.create_index(op.f("ix_sports_updates_scope"), "sports_updates", ["scope"], unique=False)
    op.create_index(op.f("ix_sports_updates_last_attempted_at"), "sports_updates", ["last_attempted_at"], unique=False)

    op.create_table(
        "sports_update_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sports_update_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["sports_update_id"], ["sports_updates.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sports_update_id", "team_id", name="uq_sports_update_teams_update_team"),
    )
    op.create_index(op.f("ix_sports_update_teams_id"), "sports_update_teams", ["id"], unique=False)
    op.create_index("ix_sports_update_teams_team", "sports_update_teams", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sports_update_teams_team", table_name="sports_update_teams")
    op.drop_index(op.f("ix_sports_update_teams_id"), table_name="sports_update_teams")
    op.drop_table("sports_update_teams")

    op.drop_index(op.f("ix_sports_updates_last_attempted_at"), table_name="sports_updates")
    op.drop_index(op.f("ix_sports_updates_scope"), table_name="sports_updates")
    op.drop_index(op.f("ix_sports_updates_league"), table_name="sports_updates")
    op.drop_index(op.f("ix_sports_updates_classifier_status"), table_name="sports_updates")
    op.drop_index("ix_sports_updates_scope_league", table_name="sports_updates")
    op.drop_index("ix_sports_updates_status_created", table_name="sports_updates")
    op.drop_index(op.f("ix_sports_updates_id"), table_name="sports_updates")
    op.drop_table("sports_updates")

    op.drop_index(op.f("ix_sports_update_source_items_feed_key"), table_name="sports_update_source_items")
    op.drop_index("ix_sports_update_source_items_league_published", table_name="sports_update_source_items")
    op.drop_index(op.f("ix_sports_update_source_items_id"), table_name="sports_update_source_items")
    op.drop_table("sports_update_source_items")

    op.drop_index(op.f("ix_user_league_follows_id"), table_name="user_league_follows")
    op.drop_table("user_league_follows")
