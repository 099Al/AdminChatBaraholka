"""add is_repeated to messages

Revision ID: add_is_repeated_to_messages
Revises: add_media_group_id_to_messages
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "add_is_repeated_to_messages"
down_revision: Union[str, Sequence[str], None] = "add_media_group_id_to_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "is_repeated" not in columns:
        op.add_column("messages", sa.Column("is_repeated", sa.Integer(), nullable=True, server_default="0"))
        op.execute("UPDATE messages SET is_repeated = 0 WHERE is_repeated IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "is_repeated" in columns:
        op.drop_column("messages", "is_repeated")
