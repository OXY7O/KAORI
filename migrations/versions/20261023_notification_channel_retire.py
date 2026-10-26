"""Persist terminal Notification Channel retirement without deleting delivery evidence.

Revision ID: 20261023_channel_retire
Revises: 20261023_scope_policy_storage
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_channel_retire'
down_revision = '20261023_scope_policy_storage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'notification_channels',
        sa.Column('lifecycle_state', sa.String(length=16), server_default='active', nullable=False),
    )
    op.add_column('notification_channels', sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'notification_channels',
        sa.Column(
            'retired_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.add_column('notification_channels', sa.Column('retirement_reason', sa.String(length=500), nullable=True))
    op.create_check_constraint(
        'ck_notification_channels_lifecycle_state',
        'notification_channels',
        "lifecycle_state IN ('active', 'retired')",
    )
    op.create_index(
        'ix_notification_channels_lifecycle_enabled',
        'notification_channels',
        ['lifecycle_state', 'enabled'],
    )


def downgrade() -> None:
    op.drop_index('ix_notification_channels_lifecycle_enabled', table_name='notification_channels')
    op.drop_constraint(
        'ck_notification_channels_lifecycle_state',
        'notification_channels',
        type_='check',
    )
    op.drop_column('notification_channels', 'retirement_reason')
    op.drop_column('notification_channels', 'retired_by_user_id')
    op.drop_column('notification_channels', 'retired_at')
    op.drop_column('notification_channels', 'lifecycle_state')
