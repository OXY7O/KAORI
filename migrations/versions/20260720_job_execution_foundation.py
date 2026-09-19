"""add canonical asynchronous job execution foundation

Revision ID: 20260720_job_execution
Revises: 20260720_binding_selectors
Create Date: 2026-07-20 15:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260720_job_execution'
down_revision = '20260720_binding_selectors'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'job_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('job_type', sa.String(length=80), nullable=False),
        sa.Column('operation', sa.String(length=80), nullable=False),
        sa.Column('workload_class', sa.String(length=40), nullable=False, server_default='standard'),
        sa.Column('queue_name', sa.String(length=80), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='queued'),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('provider_type', sa.String(length=80), nullable=True),
        sa.Column('provider_instance_id', sa.Integer(), nullable=True),
        sa.Column('scope_type', sa.String(length=80), nullable=True),
        sa.Column('scope_key', sa.String(length=255), nullable=True),
        sa.Column('resource_group', sa.String(length=255), nullable=True),
        sa.Column('deduplication_key', sa.String(length=255), nullable=False),
        sa.Column('active_deduplication_key', sa.String(length=255), nullable=True),
        sa.Column('parameter_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=64), nullable=True),
        sa.Column('parent_job_id', sa.Integer(), nullable=True),
        sa.Column('progress_current', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress_message', sa.String(length=255), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('error_code', sa.String(length=80), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_type', sa.String(length=80), nullable=True),
        sa.Column('result_reference', sa.String(length=500), nullable=True),
        sa.Column('result_summary_json', sa.JSON(), nullable=True),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['parent_job_id'], ['job_executions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('active_deduplication_key'),
        sa.UniqueConstraint('celery_task_id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_job_executions_status_queue', 'job_executions', ['status', 'queue_name'])
    op.create_index('ix_job_executions_type_created', 'job_executions', ['job_type', 'created_at'])
    op.create_index('ix_job_executions_resource_status', 'job_executions', ['resource_group', 'status'])
    op.create_index('ix_job_executions_requester_status', 'job_executions', ['requested_by_user_id', 'status'])
    op.create_index('ix_job_executions_deduplication', 'job_executions', ['deduplication_key'])
    op.create_index('ix_job_executions_job_type', 'job_executions', ['job_type'])
    op.create_index('ix_job_executions_operation', 'job_executions', ['operation'])
    op.create_index('ix_job_executions_workload_class', 'job_executions', ['workload_class'])
    op.create_index('ix_job_executions_queue_name', 'job_executions', ['queue_name'])
    op.create_index('ix_job_executions_status', 'job_executions', ['status'])
    op.create_index('ix_job_executions_requested_by_user_id', 'job_executions', ['requested_by_user_id'])
    op.create_index('ix_job_executions_provider_type', 'job_executions', ['provider_type'])
    op.create_index('ix_job_executions_provider_instance_id', 'job_executions', ['provider_instance_id'])
    op.create_index('ix_job_executions_scope_type', 'job_executions', ['scope_type'])
    op.create_index('ix_job_executions_scope_key', 'job_executions', ['scope_key'])
    op.create_index('ix_job_executions_resource_group', 'job_executions', ['resource_group'])
    op.create_index('ix_job_executions_celery_task_id', 'job_executions', ['celery_task_id'])
    op.create_index('ix_job_executions_parent_job_id', 'job_executions', ['parent_job_id'])
    op.create_index('ix_job_executions_heartbeat_at', 'job_executions', ['heartbeat_at'])
    op.create_index('ix_job_executions_expires_at', 'job_executions', ['expires_at'])

    op.create_table(
        'job_execution_subscribers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_execution_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notify_on_completion', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('subscribed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['job_execution_id'], ['job_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_execution_id', 'user_id', name='uq_job_execution_subscriber'),
    )
    op.create_index('ix_job_execution_subscribers_user', 'job_execution_subscribers', ['user_id', 'subscribed_at'])
    op.create_index('ix_job_execution_subscribers_job_execution_id', 'job_execution_subscribers', ['job_execution_id'])
    op.create_index('ix_job_execution_subscribers_user_id', 'job_execution_subscribers', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_job_execution_subscribers_user_id', table_name='job_execution_subscribers')
    op.drop_index('ix_job_execution_subscribers_job_execution_id', table_name='job_execution_subscribers')
    op.drop_index('ix_job_execution_subscribers_user', table_name='job_execution_subscribers')
    op.drop_table('job_execution_subscribers')

    op.drop_index('ix_job_executions_expires_at', table_name='job_executions')
    op.drop_index('ix_job_executions_heartbeat_at', table_name='job_executions')
    op.drop_index('ix_job_executions_parent_job_id', table_name='job_executions')
    op.drop_index('ix_job_executions_celery_task_id', table_name='job_executions')
    op.drop_index('ix_job_executions_resource_group', table_name='job_executions')
    op.drop_index('ix_job_executions_scope_key', table_name='job_executions')
    op.drop_index('ix_job_executions_scope_type', table_name='job_executions')
    op.drop_index('ix_job_executions_provider_instance_id', table_name='job_executions')
    op.drop_index('ix_job_executions_provider_type', table_name='job_executions')
    op.drop_index('ix_job_executions_requested_by_user_id', table_name='job_executions')
    op.drop_index('ix_job_executions_status', table_name='job_executions')
    op.drop_index('ix_job_executions_queue_name', table_name='job_executions')
    op.drop_index('ix_job_executions_workload_class', table_name='job_executions')
    op.drop_index('ix_job_executions_operation', table_name='job_executions')
    op.drop_index('ix_job_executions_job_type', table_name='job_executions')
    op.drop_index('ix_job_executions_deduplication', table_name='job_executions')
    op.drop_index('ix_job_executions_requester_status', table_name='job_executions')
    op.drop_index('ix_job_executions_resource_status', table_name='job_executions')
    op.drop_index('ix_job_executions_type_created', table_name='job_executions')
    op.drop_index('ix_job_executions_status_queue', table_name='job_executions')
    op.drop_table('job_executions')
