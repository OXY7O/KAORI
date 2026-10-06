"""add per-user timezone preference

Revision ID: 20260711_user_timezone
Revises: 20260710_notifications
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_user_timezone'
down_revision: str | None = '20260710_notifications'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'timezone',
            sa.String(length=100),
            nullable=False,
            server_default='UTC',
        ),
    )
    op.alter_column('users', 'timezone', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'timezone')
