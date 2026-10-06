"""move scheduled report delivery to configured notification channels

Revision ID: 20260814_report_notify_channels
Revises: 20260814_intel_notify_channels
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260814_report_notify_channels'
down_revision = '20260814_intel_notify_channels'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'report_schedules',
        'notification_channels',
        existing_type=sa.JSON(),
        new_column_name='notification_channel_ids',
        existing_nullable=False,
    )
    # Legacy values were provider keys (for example ``telegram``), not channel identities.
    # Reset them rather than guessing which newly configured destination should receive a report.
    op.execute("UPDATE report_schedules SET notification_channel_ids = '[]'::json")


def downgrade() -> None:
    op.alter_column(
        'report_schedules',
        'notification_channel_ids',
        existing_type=sa.JSON(),
        new_column_name='notification_channels',
        existing_nullable=False,
    )
    op.execute("UPDATE report_schedules SET notification_channels = '[]'::json")
