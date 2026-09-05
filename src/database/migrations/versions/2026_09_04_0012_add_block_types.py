"""add block types

Revision ID: add_block_types
Revises: add_is_repeated_to_messages
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "add_block_types"
down_revision: Union[str, Sequence[str], None] = "add_is_repeated_to_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "block_types" not in inspector.get_table_names():
        op.create_table(
            "block_types",
            sa.Column("block_type", sa.Integer(), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
        )
    op.execute(
        "INSERT OR IGNORE INTO block_types (block_type, name, description) "
        "VALUES (1, 'limit', 'Превышение лимита объявлений')"
    )
    op.execute(
        "INSERT OR IGNORE INTO block_types (block_type, name, description) "
        "VALUES (2, 'repeat', 'Повторное объявление')"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "block_types" in inspector.get_table_names():
        op.drop_table("block_types")
