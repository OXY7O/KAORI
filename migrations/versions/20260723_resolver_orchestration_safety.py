"""Add distributed resolver orchestration safety state.

Revision ID: 20260723_resolver_orchestration
Revises: 20260723_decision_workflow
Create Date: 2026-07-23 17:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260723_resolver_orchestration'
down_revision = '20260723_decision_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('intelligence_execution_journal') as batch:
        batch.add_column(sa.Column('idempotency_key', sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column('orchestration_status', sa.String(length=30), nullable=False, server_default='pending')
        )
        batch.add_column(
            sa.Column('queue_name', sa.String(length=80), nullable=False, server_default='resolver-execution')
        )
        batch.add_column(sa.Column('celery_task_id', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('lease_owner', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('lease_acquired_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'))
        batch.add_column(sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('last_error_code', sa.String(length=80), nullable=True))
        batch.create_check_constraint(
            'ck_intelligence_execution_orchestration_status',
            "orchestration_status IN ('pending', 'queued', 'running', 'retry_wait', 'completed', 'dead_letter')",
        )
        batch.create_unique_constraint('uq_intelligence_execution_idempotency', ['idempotency_key'])
        batch.create_unique_constraint('uq_intelligence_execution_celery_task_id', ['celery_task_id'])
        batch.create_index('ix_intelligence_execution_orchestration_status', ['orchestration_status'])
        batch.create_index('ix_intelligence_execution_orchestration_due', ['orchestration_status', 'next_retry_at'])
        batch.create_index('ix_intelligence_execution_lease_expiry', ['lease_expires_at'])


def downgrade() -> None:
    with op.batch_alter_table('intelligence_execution_journal') as batch:
        batch.drop_index('ix_intelligence_execution_lease_expiry')
        batch.drop_index('ix_intelligence_execution_orchestration_due')
        batch.drop_index('ix_intelligence_execution_orchestration_status')
        batch.drop_constraint('uq_intelligence_execution_celery_task_id', type_='unique')
        batch.drop_constraint('uq_intelligence_execution_idempotency', type_='unique')
        batch.drop_constraint('ck_intelligence_execution_orchestration_status', type_='check')
        for name in (
            'last_error_code',
            'next_retry_at',
            'max_attempts',
            'attempt_count',
            'last_heartbeat_at',
            'lease_expires_at',
            'lease_acquired_at',
            'lease_owner',
            'celery_task_id',
            'queue_name',
            'orchestration_status',
            'idempotency_key',
        ):
            batch.drop_column(name)
