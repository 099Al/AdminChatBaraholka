"""add flood block type

Revision ID: add_flood_block_type
Revises: add_format_notice_sent_at
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_flood_block_type"
down_revision: Union[str, Sequence[str], None] = "add_format_notice_sent_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT OR IGNORE INTO block_types (block_type, name, description) "
        "VALUES (3, 'flood', 'Флуд')"
    )
    op.execute(
        "UPDATE block_types "
        "SET name = 'flood', description = 'Флуд' "
        "WHERE block_type = 3"
    )


def downgrade() -> None:
    op.execute("DELETE FROM block_types WHERE block_type = 3")
