"""add blocked_until to user_banned

Revision ID: add_blocked_until_user_banned
Revises: f9cf68e90372
Create Date: 2026-08-31 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_blocked_until_user_banned"
down_revision: Union[str, Sequence[str], None] = "f9cf68e90372"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_banned")}
    if "blocked_until" not in columns:
        op.add_column("user_banned", sa.Column("blocked_until", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_banned")}
    if "blocked_until" in columns:
        op.drop_column("user_banned", "blocked_until")
