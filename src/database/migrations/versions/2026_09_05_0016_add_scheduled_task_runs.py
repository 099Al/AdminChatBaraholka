"""add scheduled task runs

Revision ID: 2026_09_05_0016
Revises: 2026_09_05_0015
Create Date: 2026-09-05 00:16:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_09_05_0016"
down_revision: Union[str, None] = "2026_09_05_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_task_runs",
        sa.Column("task_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.Text(), nullable=True),
        sa.Column("next_run_at", sa.Text(), nullable=True),
        sa.Column("last_status", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("task_key"),
    )


def downgrade() -> None:
    op.drop_table("scheduled_task_runs")
