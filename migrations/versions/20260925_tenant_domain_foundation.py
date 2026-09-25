"""add provider-neutral tenant domain foundation

Revision ID: 20260925_tenant_domain
Revises: 20260823_rule_exceptions
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = '20260925_tenant_domain'
down_revision = '20260823_rule_exceptions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('lifecycle_status', sa.String(length=30), nullable=False),
        sa.Column('ownership_status', sa.String(length=30), nullable=False),
        sa.Column('provider_key', sa.String(length=40), nullable=False),
        sa.Column('provider_state', sa.String(length=40), nullable=False),
        sa.Column('reconciliation_authority', sa.String(length=40), nullable=False),
        sa.Column('provider_reference', sa.String(length=255), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('provider_evidence_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider_key IN ('native_kubernetes', 'capsule')", name='ck_tenants_provider_key'),
        sa.CheckConstraint(
            "provider_state IN ('native', 'capsule', 'capsule_degraded', 'native_recovery')",
            name='ck_tenants_provider_state',
        ),
        sa.CheckConstraint(
            "ownership_status IN ('managed', 'discovered', 'adopted')", name='ck_tenants_ownership_status'
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('pending', 'ready', 'degraded', 'decommissioning', 'decommissioned')",
            name='ck_tenants_lifecycle_status',
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster_id', 'slug', name='uq_tenants_cluster_slug'),
        sa.UniqueConstraint('correlation_id', name='uq_tenants_correlation_id'),
    )
    op.create_index('ix_tenants_cluster_lifecycle', 'tenants', ['cluster_id', 'lifecycle_status'])
    op.create_index('ix_tenants_provider_state', 'tenants', ['provider_key', 'provider_state'])

    op.create_table(
        'tenant_environments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('environment', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "environment IN ('development', 'staging', 'production')", name='ck_tenant_environments_environment'
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'environment', name='uq_tenant_environments_tenant_environment'),
    )

    op.create_table(
        'tenant_namespaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('namespace', sa.String(length=253), nullable=False),
        sa.Column('ownership_status', sa.String(length=30), nullable=False),
        sa.Column('provider_reference', sa.String(length=255), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ownership_status IN ('managed', 'discovered', 'adopted')", name='ck_tenant_namespaces_ownership_status'
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster_id', 'namespace', name='uq_tenant_namespaces_cluster_namespace'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_namespaces_correlation_id'),
    )
    op.create_index('ix_tenant_namespaces_environment', 'tenant_namespaces', ['tenant_environment_id', 'namespace'])


def downgrade() -> None:
    op.drop_table('tenant_namespaces')
    op.drop_table('tenant_environments')
    op.drop_table('tenants')
