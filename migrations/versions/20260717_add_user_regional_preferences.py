"""add per-user regional presentation preferences

Revision ID: 20260717_user_regional
Revises: 20260717_auth_activity
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260717_user_regional'
down_revision = '20260717_auth_activity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('timezone_mode', sa.String(length=20), nullable=False, server_default='manual'),
    )
    op.add_column(
        'users',
        sa.Column('locale', sa.String(length=20), nullable=False, server_default='en-US'),
    )
    op.add_column(
        'users',
        sa.Column('date_format', sa.String(length=30), nullable=False, server_default='day_month_year'),
    )
    op.add_column(
        'users',
        sa.Column('time_format', sa.String(length=10), nullable=False, server_default='24h'),
    )

    op.alter_column('users', 'timezone_mode', server_default=None)
    op.alter_column('users', 'locale', server_default=None)
    op.alter_column('users', 'date_format', server_default=None)
    op.alter_column('users', 'time_format', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'time_format')
    op.drop_column('users', 'date_format')
    op.drop_column('users', 'locale')
    op.drop_column('users', 'timezone_mode')
