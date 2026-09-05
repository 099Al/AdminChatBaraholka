"""add reply_to_message_id to messages

Revision ID: add_reply_to_message_id
Revises: add_limit_block_fields
Create Date: 2026-08-31 00:09:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_reply_to_message_id"
down_revision: Union[str, Sequence[str], None] = "add_limit_block_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "reply_to_message_id" not in columns:
        op.add_column("messages", sa.Column("reply_to_message_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "reply_to_message_id" in columns:
        op.drop_column("messages", "reply_to_message_id")
