"""rename message text columns

Revision ID: rename_message_text_columns
Revises: add_is_blocked_user_banned
Create Date: 2026-08-31 00:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "rename_message_text_columns"
down_revision: Union[str, Sequence[str], None] = "add_is_blocked_user_banned"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("messages")}


def upgrade() -> None:
    """Upgrade schema."""
    columns = _columns()
    if "message_short" in columns and "text_short" not in columns:
        op.alter_column("messages", "message_short", new_column_name="text_short")
        columns.remove("message_short")
        columns.add("text_short")

    if "message_hash" in columns and "text_full_hash" not in columns:
        op.alter_column("messages", "message_hash", new_column_name="text_full_hash")
        columns.remove("message_hash")
        columns.add("text_full_hash")

    if "text_full_hash" not in columns:
        op.add_column("messages", sa.Column("text_full_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    columns = _columns()
    if "text_full_hash" in columns and "message_hash" not in columns:
        op.alter_column("messages", "text_full_hash", new_column_name="message_hash")
        columns.remove("text_full_hash")
        columns.add("message_hash")

    if "text_short" in columns and "message_short" not in columns:
        op.alter_column("messages", "text_short", new_column_name="message_short")
