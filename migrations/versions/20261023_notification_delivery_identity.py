"""Reserve durable Notification Delivery identities without activating cleanup.

Revision ID: 20261023_delivery_identity
Revises: 20261023_notify_retry_after

Schema-only. Does not backfill or change dispatch, channel deletion, archive
policy, recovery worker, or retention. Existing delivery journal remains
authoritative until #2868 runtime/atomic rollout is separately admitted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_delivery_identity'
down_revision = '20261023_notify_retry_after'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notification_delivery_identities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'channel_id',
            sa.Integer(),
            sa.ForeignKey('notification_channels.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('event_key', sa.String(255), nullable=False),
        sa.Column('source_delivery_id', sa.Integer(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            'channel_id',
            'event_key',
            name='uq_notification_delivery_identity_event',
        ),
        sa.UniqueConstraint(
            'source_delivery_id',
            name='uq_notification_delivery_identities_source_delivery_id',
        ),
    )
    op.create_index(
        'ix_notification_delivery_identities_channel_id',
        'notification_delivery_identities',
        ['channel_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_notification_delivery_identities_channel_id',
        table_name='notification_delivery_identities',
    )
    op.drop_table('notification_delivery_identities')
