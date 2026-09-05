"""add media_group_id to messages

Revision ID: add_media_group_id_to_messages
Revises: add_reply_to_message_id
Create Date: 2026-09-02 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "add_media_group_id_to_messages"
down_revision: Union[str, Sequence[str], None] = "add_reply_to_message_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "media_group_id" not in columns:
        op.add_column("messages", sa.Column("media_group_id", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "media_group_id" in columns:
        op.drop_column("messages", "media_group_id")
