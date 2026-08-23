"""add fast alert signal snapshots

Revision ID: 20260823_alert_signal_eval
Revises: 20260823_alert_false_positive
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from alembic import op

revision = '20260823_alert_signal_eval'
down_revision = '20260823_alert_false_positive'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alert_signal_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=40), nullable=False),
        sa.Column('asset_key', sa.String(length=80), nullable=False),
        sa.Column('signal_key', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ready'),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('ready', 'failed')", name='ck_alert_signal_snapshot_status'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'asset_key', 'signal_key', name='uq_alert_signal_snapshot_scope'),
    )
    op.create_index('ix_alert_signal_snapshot_asset_key', 'alert_signal_snapshots', ['asset_key'])
    op.create_index('ix_alert_signal_snapshot_domain', 'alert_signal_snapshots', ['domain'])
    op.create_index('ix_alert_signal_snapshot_signal_key', 'alert_signal_snapshots', ['signal_key'])
    op.create_index('ix_alert_signal_snapshot_status', 'alert_signal_snapshots', ['status'])
    op.create_index('ix_alert_signal_snapshot_expires_at', 'alert_signal_snapshots', ['expires_at'])
    op.create_index(
        'ix_alert_signal_snapshot_lookup',
        'alert_signal_snapshots',
        ['domain', 'asset_key', 'signal_key'],
    )
    op.create_index(
        'ix_alert_signal_snapshot_freshness',
        'alert_signal_snapshots',
        ['status', 'expires_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_alert_signal_snapshot_freshness', table_name='alert_signal_snapshots')
    op.drop_index('ix_alert_signal_snapshot_lookup', table_name='alert_signal_snapshots')
    op.drop_index('ix_alert_signal_snapshot_expires_at', table_name='alert_signal_snapshots')
    op.drop_index('ix_alert_signal_snapshot_status', table_name='alert_signal_snapshots')
    op.drop_index('ix_alert_signal_snapshot_signal_key', table_name='alert_signal_snapshots')
    op.drop_index('ix_alert_signal_snapshot_domain', table_name='alert_signal_snapshots')
    op.drop_index('ix_alert_signal_snapshot_asset_key', table_name='alert_signal_snapshots')
    op.drop_table('alert_signal_snapshots')
