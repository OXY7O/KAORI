"""separate Activity Audit records from Notification Deck visibility

Revision ID: 20260805_notification_deck_v2
Revises: 20260805_secret_ops_v2
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op

revision = '20260805_notification_deck_v2'
down_revision = '20260805_secret_ops_v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'notifications',
        sa.Column(
            'deck_visible',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index(
        'ix_notifications_user_deck_created',
        'notifications',
        ['user_id', 'deck_visible', 'created_at'],
        unique=False,
    )
    op.alter_column('notifications', 'deck_visible', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_notifications_user_deck_created', table_name='notifications')
    op.drop_column('notifications', 'deck_visible')
