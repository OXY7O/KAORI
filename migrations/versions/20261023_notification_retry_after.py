"""Persist an indexed Notification Delivery retry due-time (#1475).

Revision ID: 20261023_notify_retry_after
Revises: 20261023_sc_webhook_job_link

Existing rows retain NULL and the legacy global backoff semantics.
Recovery remains disabled by default; no worker or provider send is enabled.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_notify_retry_after'
down_revision = '20261023_sc_webhook_job_link'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'notification_deliveries',
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_notification_deliveries_status_next_retry',
        'notification_deliveries',
        ['status', 'next_retry_at'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_notification_deliveries_status_next_retry',
        table_name='notification_deliveries',
    )
    op.drop_column('notification_deliveries', 'next_retry_at')
