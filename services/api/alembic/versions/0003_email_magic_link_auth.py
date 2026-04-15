"""email magic-link auth

Revision ID: 0003_email_magic_link_auth
Revises: 0002_add_game_odds_current
Create Date: 2026-04-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_email_magic_link_auth"
down_revision: Union[str, None] = "0002_add_game_odds_current"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_login_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column("requested_user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_email_login_tokens_token_hash", "email_login_tokens", ["token_hash"])
    op.create_index("ix_email_login_tokens_email", "email_login_tokens", ["email"])
    op.create_index("ix_email_login_tokens_expires_at", "email_login_tokens", ["expires_at"])
    op.create_index("ix_email_login_tokens_consumed_at", "email_login_tokens", ["consumed_at"])
    op.create_index("ix_email_login_tokens_created_at", "email_login_tokens", ["created_at"])

    op.drop_column("users", "password_hash")


def downgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET password_hash = 'removed'")
    op.alter_column("users", "password_hash", nullable=False)

    op.drop_index("ix_email_login_tokens_created_at", table_name="email_login_tokens")
    op.drop_index("ix_email_login_tokens_consumed_at", table_name="email_login_tokens")
    op.drop_index("ix_email_login_tokens_expires_at", table_name="email_login_tokens")
    op.drop_index("ix_email_login_tokens_email", table_name="email_login_tokens")
    op.drop_constraint("uq_email_login_tokens_token_hash", "email_login_tokens", type_="unique")
    op.drop_table("email_login_tokens")
