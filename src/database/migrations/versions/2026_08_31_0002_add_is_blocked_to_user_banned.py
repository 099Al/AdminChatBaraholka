"""add is_blocked to user_banned

Revision ID: add_is_blocked_user_banned
Revises: add_blocked_until_user_banned
Create Date: 2026-08-31 00:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_is_blocked_user_banned"
down_revision: Union[str, Sequence[str], None] = "add_blocked_until_user_banned"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_banned")}
    if "is_blocked" not in columns:
        op.add_column(
            "user_banned",
            sa.Column("is_blocked", sa.Integer(), nullable=False, server_default="0"),
        )
        op.execute(
            "UPDATE user_banned "
            "SET is_blocked = 1 "
            "WHERE blocked_until IS NOT NULL AND blocked_until != ''"
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_banned")}
    if "is_blocked" in columns:
        op.drop_column("user_banned", "is_blocked")
