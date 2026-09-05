"""add original_author to messages

Revision ID: add_original_author_to_messages
Revises: add_image_hash_to_messages
Create Date: 2026-08-31 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_original_author_to_messages"
down_revision: Union[str, Sequence[str], None] = "add_image_hash_to_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "original_author" not in columns:
        op.add_column("messages", sa.Column("original_author", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "original_author" in columns:
        op.drop_column("messages", "original_author")
