"""add provider-neutral notification channels

Revision ID: 20260814_intel_notify_channels
Revises: 20260814_obj_alert_profile
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260814_intel_notify_channels'
down_revision = '20260814_obj_alert_profile'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notification_channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('provider_key', sa.String(length=40), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('credential_payload', sa.Text(), nullable=True),
        sa.Column('destination', sa.String(length=255), nullable=True),
        sa.Column('provider_config', sa.JSON(), nullable=False),
        sa.Column('minimum_severity', sa.String(length=20), nullable=False),
        sa.Column('domains', sa.JSON(), nullable=False),
        sa.Column('event_types', sa.JSON(), nullable=False),
        sa.Column('test_status', sa.String(length=20), nullable=False),
        sa.Column('test_message', sa.String(length=500), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_delivery_status', sa.String(length=20), nullable=False),
        sa.Column('last_delivery_message', sa.String(length=500), nullable=True),
        sa.Column('last_delivery_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_delivery_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "minimum_severity IN ('critical', 'warning', 'info')",
            name='ck_notification_channels_minimum_severity',
        ),
        sa.CheckConstraint(
            "test_status IN ('not_tested', 'success', 'failed')",
            name='ck_notification_channels_test_status',
        ),
        sa.CheckConstraint(
            "last_delivery_status IN ('never', 'success', 'failed')",
            name='ck_notification_channels_delivery_status',
        ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_notification_channels_provider_enabled', 'notification_channels', ['provider_key', 'enabled'])

    op.create_table(
        'notification_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('event_key', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=120), nullable=False),
        sa.Column('domain', sa.String(length=80), nullable=False),
        sa.Column('asset_type', sa.String(length=80), nullable=False),
        sa.Column('asset_key', sa.String(length=255), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('provider_message_id', sa.String(length=120), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'sent', 'failed', 'skipped')",
            name='ck_notification_deliveries_status',
        ),
        sa.ForeignKeyConstraint(['channel_id'], ['notification_channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id', 'event_key', name='uq_notification_delivery_event'),
    )
    op.create_index('ix_notification_deliveries_channel_id', 'notification_deliveries', ['channel_id'])
    op.create_index('ix_notification_deliveries_domain', 'notification_deliveries', ['domain'])
    op.create_index('ix_notification_deliveries_asset_key', 'notification_deliveries', ['asset_key'])
    op.create_index('ix_notification_deliveries_status_created', 'notification_deliveries', ['status', 'created_at'])
    op.create_index('ix_notification_deliveries_domain_asset', 'notification_deliveries', ['domain', 'asset_key'])


def downgrade() -> None:
    op.drop_index('ix_notification_deliveries_domain_asset', table_name='notification_deliveries')
    op.drop_index('ix_notification_deliveries_status_created', table_name='notification_deliveries')
    op.drop_index('ix_notification_deliveries_asset_key', table_name='notification_deliveries')
    op.drop_index('ix_notification_deliveries_domain', table_name='notification_deliveries')
    op.drop_index('ix_notification_deliveries_channel_id', table_name='notification_deliveries')
    op.drop_table('notification_deliveries')
    op.drop_index('ix_notification_channels_provider_enabled', table_name='notification_channels')
    op.drop_table('notification_channels')
