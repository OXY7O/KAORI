"""add Artifact Registry governance, webhook, and analytics evidence

Revision ID: 20261004_registry_governance
Revises: 20261004_registry_runtime
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20261004_registry_governance'
down_revision = '20261004_registry_runtime'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'registry_governance_states',
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('capability_states', sa.JSON(), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('integration_instance_id'),
    )
    op.alter_column('registry_governance_states', 'status', server_default=None)

    op.create_table(
        'registry_project_governance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('retention_status', sa.String(length=40), nullable=False, server_default='not_collected'),
        sa.Column('retention_policy_ref', sa.String(length=255), nullable=True),
        sa.Column('retention_summary', sa.JSON(), nullable=True),
        sa.Column('immutability_status', sa.String(length=40), nullable=False, server_default='not_collected'),
        sa.Column('immutability_rule_count', sa.Integer(), nullable=True),
        sa.Column('immutability_summary', sa.JSON(), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['registry_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_registry_project_governance_project'),
    )
    op.alter_column('registry_project_governance', 'retention_status', server_default=None)
    op.alter_column('registry_project_governance', 'immutability_status', server_default=None)
    op.create_index('ix_registry_project_governance_project_id', 'registry_project_governance', ['project_id'])
    op.create_index('ix_registry_project_governance_observed', 'registry_project_governance', ['observed_at'])

    op.create_table(
        'registry_replication_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('trigger_type', sa.String(length=80), nullable=True),
        sa.Column('source_registry', sa.String(length=255), nullable=True),
        sa.Column('destination_registry', sa.String(length=255), nullable=True),
        sa.Column('destination_namespace', sa.String(length=512), nullable=True),
        sa.Column('filters_json', sa.JSON(), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'integration_instance_id',
            'provider_native_id',
            name='uq_registry_replication_instance_native',
        ),
    )
    op.create_index(
        'ix_registry_replication_policies_integration_instance_id',
        'registry_replication_policies',
        ['integration_instance_id'],
    )
    op.create_index(
        'ix_registry_replication_instance_observed',
        'registry_replication_policies',
        ['integration_instance_id', 'observed_at'],
    )

    op.create_table(
        'registry_webhook_endpoints',
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('token_digest', sa.String(length=128), nullable=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=40), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('integration_instance_id'),
    )
    op.alter_column('registry_webhook_endpoints', 'enabled', server_default=None)

    op.create_table(
        'registry_webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('dedup_key', sa.String(length=128), nullable=False),
        sa.Column('provider_event_id', sa.String(length=255), nullable=True),
        sa.Column('event_type', sa.String(length=120), nullable=False),
        sa.Column('payload_digest', sa.String(length=128), nullable=False),
        sa.Column('project_name', sa.String(length=255), nullable=True),
        sa.Column('repository_name', sa.String(length=512), nullable=True),
        sa.Column('artifact_digest', sa.String(length=255), nullable=True),
        sa.Column('artifact_tag', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='received'),
        sa.Column('job_execution_id', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_execution_id'], ['job_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'integration_instance_id',
            'dedup_key',
            name='uq_registry_webhook_event_dedup',
        ),
    )
    op.alter_column('registry_webhook_events', 'status', server_default=None)
    op.create_index(
        'ix_registry_webhook_events_integration_instance_id', 'registry_webhook_events', ['integration_instance_id']
    )
    op.create_index('ix_registry_webhook_events_job_execution_id', 'registry_webhook_events', ['job_execution_id'])
    op.create_index(
        'ix_registry_webhook_events_instance_received',
        'registry_webhook_events',
        ['integration_instance_id', 'received_at'],
    )
    op.create_index('ix_registry_webhook_events_status', 'registry_webhook_events', ['status'])


def downgrade() -> None:
    op.drop_index('ix_registry_webhook_events_status', table_name='registry_webhook_events')
    op.drop_index('ix_registry_webhook_events_instance_received', table_name='registry_webhook_events')
    op.drop_index('ix_registry_webhook_events_job_execution_id', table_name='registry_webhook_events')
    op.drop_index('ix_registry_webhook_events_integration_instance_id', table_name='registry_webhook_events')
    op.drop_table('registry_webhook_events')
    op.drop_table('registry_webhook_endpoints')
    op.drop_index('ix_registry_replication_instance_observed', table_name='registry_replication_policies')
    op.drop_index(
        'ix_registry_replication_policies_integration_instance_id', table_name='registry_replication_policies'
    )
    op.drop_table('registry_replication_policies')
    op.drop_index('ix_registry_project_governance_observed', table_name='registry_project_governance')
    op.drop_index('ix_registry_project_governance_project_id', table_name='registry_project_governance')
    op.drop_table('registry_project_governance')
    op.drop_table('registry_governance_states')
