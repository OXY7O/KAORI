"""add Tenant capacity governance policy and decisions

Revision ID: 20260925_tenant_capacity
Revises: 20260925_tenant_profile_lineage
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = '20260925_tenant_capacity'
down_revision = '20260925_tenant_profile_lineage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_capacity_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('system_reserved_cpu', sa.String(length=32), nullable=False, server_default='0'),
        sa.Column('system_reserved_memory', sa.String(length=32), nullable=False, server_default='0'),
        sa.Column('safety_headroom_percent', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('unmanaged_cpu_requests', sa.String(length=32), nullable=False, server_default='0'),
        sa.Column('unmanaged_memory_requests', sa.String(length=32), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'safety_headroom_percent >= 0 AND safety_headroom_percent <= 100',
            name='ck_tenant_capacity_policies_headroom_percent',
        ),
        sa.CheckConstraint('version >= 1', name='ck_tenant_capacity_policies_version'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster_id', name='uq_tenant_capacity_policies_cluster'),
    )

    op.create_table(
        'tenant_capacity_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=False),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=True),
        sa.Column('resource_profile_id', sa.Integer(), nullable=True),
        sa.Column('namespace', sa.String(length=253), nullable=False),
        sa.Column('operation', sa.String(length=20), nullable=False, server_default='create'),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column('capacity_state', sa.String(length=30), nullable=False),
        sa.Column('proposal_quota_json', sa.JSON(), nullable=False),
        sa.Column('evidence_json', sa.JSON(), nullable=False),
        sa.Column('data_cutoff', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('create', 'increase', 'reduce')",
            name='ck_tenant_capacity_decisions_operation',
        ),
        sa.CheckConstraint(
            "decision IN ('allow', 'block')",
            name='ck_tenant_capacity_decisions_result',
        ),
        sa.CheckConstraint(
            "capacity_state IN ('healthy', 'near_capacity', 'critical', 'exhausted', 'overcommitted', 'unknown')",
            name='ck_tenant_capacity_decisions_state',
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_profile_id'], ['tenant_resource_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_capacity_decisions_correlation_id'),
    )
    op.create_index(
        'ix_tenant_capacity_decisions_cluster_created',
        'tenant_capacity_decisions',
        ['cluster_id', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_tenant_capacity_decisions_environment_namespace',
        'tenant_capacity_decisions',
        ['tenant_environment_id', 'namespace'],
        unique=False,
    )

    op.alter_column('tenant_capacity_policies', 'system_reserved_cpu', server_default=None)
    op.alter_column('tenant_capacity_policies', 'system_reserved_memory', server_default=None)
    op.alter_column('tenant_capacity_policies', 'safety_headroom_percent', server_default=None)
    op.alter_column('tenant_capacity_policies', 'unmanaged_cpu_requests', server_default=None)
    op.alter_column('tenant_capacity_policies', 'unmanaged_memory_requests', server_default=None)
    op.alter_column('tenant_capacity_policies', 'version', server_default=None)
    op.alter_column('tenant_capacity_decisions', 'operation', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_tenant_capacity_decisions_environment_namespace', table_name='tenant_capacity_decisions')
    op.drop_index('ix_tenant_capacity_decisions_cluster_created', table_name='tenant_capacity_decisions')
    op.drop_table('tenant_capacity_decisions')
    op.drop_table('tenant_capacity_policies')
