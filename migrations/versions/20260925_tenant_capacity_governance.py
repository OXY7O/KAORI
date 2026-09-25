"""add Tenant capacity governance policy and decision history

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
        sa.Column('platform_reserve_cpu', sa.String(length=50), nullable=False),
        sa.Column('platform_reserve_memory', sa.String(length=50), nullable=False),
        sa.Column('safety_headroom_percent', sa.Integer(), nullable=False),
        sa.Column('unmanaged_commitment_cpu', sa.String(length=50), nullable=False),
        sa.Column('unmanaged_commitment_memory', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'safety_headroom_percent >= 0 AND safety_headroom_percent < 100',
            name='ck_tenant_capacity_policies_headroom_percent',
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster_id', name='uq_tenant_capacity_policies_cluster'),
    )
    op.create_index(
        'ix_tenant_capacity_policies_cluster',
        'tenant_capacity_policies',
        ['cluster_id'],
    )

    op.create_table(
        'tenant_capacity_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=True),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=True),
        sa.Column('resource_profile_id', sa.Integer(), nullable=True),
        sa.Column('resource_profile_version', sa.Integer(), nullable=True),
        sa.Column('namespace', sa.String(length=253), nullable=False),
        sa.Column('operation', sa.String(length=20), nullable=False),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column('capacity_state', sa.String(length=30), nullable=False),
        sa.Column('evidence_json', sa.JSON(), nullable=False),
        sa.Column('data_cutoff', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('create', 'increase', 'decrease', 'no_change')",
            name='ck_tenant_capacity_decisions_operation',
        ),
        sa.CheckConstraint(
            "decision IN ('allow', 'block')",
            name='ck_tenant_capacity_decisions_decision',
        ),
        sa.CheckConstraint(
            "capacity_state IN ('Healthy', 'Near Capacity', 'Critical', 'Exhausted', 'Overcommitted', 'Unknown')",
            name='ck_tenant_capacity_decisions_state',
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_profile_id'], ['tenant_resource_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_capacity_decisions_correlation_id'),
    )
    op.create_index(
        'ix_tenant_capacity_decisions_cluster_created',
        'tenant_capacity_decisions',
        ['cluster_id', 'created_at'],
    )
    op.create_index(
        'ix_tenant_capacity_decisions_result',
        'tenant_capacity_decisions',
        ['decision', 'capacity_state'],
    )


def downgrade() -> None:
    op.drop_index('ix_tenant_capacity_decisions_result', table_name='tenant_capacity_decisions')
    op.drop_index('ix_tenant_capacity_decisions_cluster_created', table_name='tenant_capacity_decisions')
    op.drop_table('tenant_capacity_decisions')
    op.drop_index('ix_tenant_capacity_policies_cluster', table_name='tenant_capacity_policies')
    op.drop_table('tenant_capacity_policies')
