"""rename cnt to block_repeat_cnt

Revision ID: rename_cnt_to_block_repeat_cnt
Revises: add_original_user_id_to_messages
Create Date: 2026-08-31 00:07:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "rename_cnt_to_block_repeat_cnt"
down_revision: Union[str, Sequence[str], None] = "add_original_user_id_to_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("user_banned")}


def upgrade() -> None:
    """Upgrade schema."""
    columns = _columns()
    if "cnt" in columns and "block_repeat_cnt" not in columns:
        op.alter_column("user_banned", "cnt", new_column_name="block_repeat_cnt")
        columns.remove("cnt")
        columns.add("block_repeat_cnt")

    if "block_repeat_cnt" not in columns:
        op.add_column(
            "user_banned",
            sa.Column("block_repeat_cnt", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    columns = _columns()
    if "block_repeat_cnt" in columns and "cnt" not in columns:
        op.alter_column("user_banned", "block_repeat_cnt", new_column_name="cnt")
