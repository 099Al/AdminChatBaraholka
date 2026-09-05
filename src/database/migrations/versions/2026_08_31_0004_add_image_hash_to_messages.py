"""add image_hash to messages

Revision ID: add_image_hash_to_messages
Revises: rename_message_text_columns
Create Date: 2026-08-31 00:04:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_image_hash_to_messages"
down_revision: Union[str, Sequence[str], None] = "rename_message_text_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "image_hash" not in columns:
        op.add_column("messages", sa.Column("image_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "image_hash" in columns:
        op.drop_column("messages", "image_hash")
