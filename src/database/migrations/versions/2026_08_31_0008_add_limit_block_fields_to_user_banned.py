"""add limit block fields to user_banned

Revision ID: add_limit_block_fields
Revises: rename_cnt_to_block_repeat_cnt
Create Date: 2026-08-31 00:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_limit_block_fields"
down_revision: Union[str, Sequence[str], None] = "rename_cnt_to_block_repeat_cnt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("user_banned")}


def upgrade() -> None:
    """Upgrade schema."""
    columns = _columns()
    if "block_limit" not in columns:
        op.add_column(
            "user_banned",
            sa.Column("block_limit", sa.Integer(), nullable=False, server_default="0"),
        )

    if "block_type" not in columns:
        op.add_column("user_banned", sa.Column("block_type", sa.Integer(), nullable=True))
        op.execute(
            "UPDATE user_banned "
            "SET block_type = 2 "
            "WHERE created_at IS NOT NULL AND created_at != ''"
        )


def downgrade() -> None:
    """Downgrade schema."""
    columns = _columns()
    if "block_type" in columns:
        op.drop_column("user_banned", "block_type")
    if "block_limit" in columns:
        op.drop_column("user_banned", "block_limit")
