"""Add scalable report schedule delivery channel state.

Revision ID: 20260729_report_delivery
Revises: 20260724_analytics_snapshot
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa

revision = '20260729_report_delivery'
down_revision = '20260724_analytics_snapshot'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'report_schedules',
        sa.Column('notification_channels', sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        'report_schedule_runs',
        sa.Column('delivery_result', sa.JSON(), nullable=True),
    )
    op.alter_column('report_schedules', 'notification_channels', server_default=None)


def downgrade() -> None:
    op.drop_column('report_schedule_runs', 'delivery_result')
    op.drop_column('report_schedules', 'notification_channels')
