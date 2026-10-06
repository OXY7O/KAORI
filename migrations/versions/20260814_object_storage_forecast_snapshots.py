"""add object storage forecast snapshots

Revision ID: 20260814_obj_forecast
Revises: 20260814_obj_metrics_profile
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260814_obj_forecast'
down_revision = '20260814_obj_metrics_profile'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'object_storage_forecast_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_storage_system_id', sa.String(length=36), nullable=False),
        sa.Column('history_window', sa.String(length=20), nullable=False),
        sa.Column('method', sa.String(length=40), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('freshness_minutes', sa.Integer(), nullable=False),
        sa.Column('stale_grace_minutes', sa.Integer(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_job_execution_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name='ck_object_storage_forecast_status',
        ),
        sa.ForeignKeyConstraint(
            ['last_job_execution_id'],
            ['job_executions.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['object_storage_system_id'],
            ['object_storage_systems.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'object_storage_system_id',
            'history_window',
            'method',
            name='uq_object_storage_forecast_scope',
        ),
    )
    op.create_index(
        'ix_object_storage_forecast_lookup',
        'object_storage_forecast_snapshots',
        ['object_storage_system_id', 'history_window', 'method'],
        unique=False,
    )
    op.create_index(
        'ix_object_storage_forecast_freshness',
        'object_storage_forecast_snapshots',
        ['status', 'expires_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_object_storage_forecast_snapshots_object_storage_system_id'),
        'object_storage_forecast_snapshots',
        ['object_storage_system_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_object_storage_forecast_snapshots_status'),
        'object_storage_forecast_snapshots',
        ['status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_object_storage_forecast_snapshots_expires_at'),
        'object_storage_forecast_snapshots',
        ['expires_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_object_storage_forecast_snapshots_last_job_execution_id'),
        'object_storage_forecast_snapshots',
        ['last_job_execution_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_object_storage_forecast_snapshots_last_job_execution_id'),
        table_name='object_storage_forecast_snapshots',
    )
    op.drop_index(
        op.f('ix_object_storage_forecast_snapshots_expires_at'),
        table_name='object_storage_forecast_snapshots',
    )
    op.drop_index(
        op.f('ix_object_storage_forecast_snapshots_status'),
        table_name='object_storage_forecast_snapshots',
    )
    op.drop_index(
        op.f('ix_object_storage_forecast_snapshots_object_storage_system_id'),
        table_name='object_storage_forecast_snapshots',
    )
    op.drop_index('ix_object_storage_forecast_freshness', table_name='object_storage_forecast_snapshots')
    op.drop_index('ix_object_storage_forecast_lookup', table_name='object_storage_forecast_snapshots')
    op.drop_table('object_storage_forecast_snapshots')
