"""add one-time codes to email login

Revision ID: 0003_add_email_login_codes
Revises: 0002_add_web_push
Create Date: 2026-07-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_email_login_codes"
down_revision: Union[str, None] = "0002_add_web_push"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM email_login_tokens")
    op.add_column(
        "email_login_tokens",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
    )
    op.add_column(
        "email_login_tokens",
        sa.Column("failed_code_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("email_login_tokens", "failed_code_attempts")
    op.drop_column("email_login_tokens", "code_hash")
