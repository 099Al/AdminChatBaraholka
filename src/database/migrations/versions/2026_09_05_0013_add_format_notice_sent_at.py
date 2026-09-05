"""add format notice sent timestamp

Revision ID: add_format_notice_sent_at
Revises: add_block_types
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "add_format_notice_sent_at"
down_revision: Union[str, Sequence[str], None] = "add_block_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_banned")}
    if "format_notice_sent_at" not in columns:
        op.add_column("user_banned", sa.Column("format_notice_sent_at", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_banned")}
    if "format_notice_sent_at" in columns:
        op.drop_column("user_banned", "format_notice_sent_at")
