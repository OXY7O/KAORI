"""add normalized Tenant Kubernetes audit observations

Revision ID: 20260927_tenant_audit
Revises: 20260926_tenant_domain_policy
Create Date: 2026-09-27
"""

import sqlalchemy as sa
from alembic import op

revision = '20260927_tenant_audit'
down_revision = '20260926_tenant_domain_policy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_kubernetes_audit_observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_uid', sa.String(length=128), nullable=False),
        sa.Column('source_id', sa.String(length=255), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('username', sa.String(length=253), nullable=False),
        sa.Column('principal_kind', sa.String(length=30), nullable=False),
        sa.Column('service_account_namespace', sa.String(length=253), nullable=True),
        sa.Column('service_account_name', sa.String(length=253), nullable=True),
        sa.Column('verb', sa.String(length=64), nullable=False),
        sa.Column('api_group', sa.String(length=253), nullable=True),
        sa.Column('api_version', sa.String(length=64), nullable=True),
        sa.Column('resource', sa.String(length=253), nullable=True),
        sa.Column('subresource', sa.String(length=253), nullable=True),
        sa.Column('namespace', sa.String(length=253), nullable=True),
        sa.Column('resource_name', sa.String(length=253), nullable=True),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=20), nullable=False),
        sa.Column('correlation_status', sa.String(length=30), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=True),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=True),
        sa.Column('membership_id', sa.Integer(), nullable=True),
        sa.Column('access_grant_id', sa.Integer(), nullable=True),
        sa.Column('credential_id', sa.Integer(), nullable=True),
        sa.Column('correlation_evidence_json', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "principal_kind IN ('service_account', 'user', 'group', 'unknown')",
            name='ck_tenant_kubernetes_audit_observations_principal_kind',
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failed', 'unknown')",
            name='ck_tenant_kubernetes_audit_observations_outcome',
        ),
        sa.CheckConstraint(
            "correlation_status IN ('managed', 'managed_revoked', 'unmanaged', 'ambiguous')",
            name='ck_tenant_kubernetes_audit_observations_correlation_status',
        ),
        sa.ForeignKeyConstraint(['access_grant_id'], ['tenant_access_grants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credential_id'], ['tenant_credentials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['membership_id'], ['tenant_memberships.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'event_uid',
            name='uq_tenant_kubernetes_audit_observations_event_uid',
        ),
    )
    op.create_index(
        'ix_tenant_kubernetes_audit_observations_scope_time',
        'tenant_kubernetes_audit_observations',
        ['cluster_id', 'namespace', 'occurred_at'],
    )
    op.create_index(
        'ix_tenant_kubernetes_audit_observations_correlation',
        'tenant_kubernetes_audit_observations',
        ['correlation_status', 'occurred_at'],
    )
    op.create_index(
        'ix_tenant_kubernetes_audit_observations_retention',
        'tenant_kubernetes_audit_observations',
        ['expires_at'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_tenant_kubernetes_audit_observations_retention',
        table_name='tenant_kubernetes_audit_observations',
    )
    op.drop_index(
        'ix_tenant_kubernetes_audit_observations_correlation',
        table_name='tenant_kubernetes_audit_observations',
    )
    op.drop_index(
        'ix_tenant_kubernetes_audit_observations_scope_time',
        table_name='tenant_kubernetes_audit_observations',
    )
    op.drop_table('tenant_kubernetes_audit_observations')
