"""add notice failed block type

Revision ID: add_notice_failed_block_type
Revises: add_flood_block_type
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_notice_failed_block_type"
down_revision: Union[str, Sequence[str], None] = "add_flood_block_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT OR IGNORE INTO block_types (block_type, name, description) "
        "VALUES (4, 'notice_failed', 'Не удалось отправить уведомление')"
    )
    op.execute(
        "UPDATE block_types "
        "SET name = 'notice_failed', description = 'Не удалось отправить уведомление' "
        "WHERE block_type = 4"
    )


def downgrade() -> None:
    op.execute("DELETE FROM block_types WHERE block_type = 4")
