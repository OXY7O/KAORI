"""add normalized Tenant Kubernetes audit correlation evidence

Revision ID: 20260927_tenant_audit_corr
Revises: 20260926_tenant_domain_policy
Create Date: 2026-09-27
"""

import sqlalchemy as sa
from alembic import op

revision = '20260927_tenant_audit_corr'
down_revision = '20260926_tenant_domain_policy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_audit_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=True),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=True),
        sa.Column('access_grant_id', sa.Integer(), nullable=True),
        sa.Column('credential_id', sa.Integer(), nullable=True),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('source_kind', sa.String(length=40), nullable=False),
        sa.Column('source_event_id', sa.String(length=160), nullable=True),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('source_reference', sa.String(length=500), nullable=True),
        sa.Column('principal_username', sa.String(length=500), nullable=False),
        sa.Column('principal_groups_json', sa.JSON(), nullable=False),
        sa.Column('principal_kind', sa.String(length=30), nullable=False),
        sa.Column('identity_class', sa.String(length=30), nullable=False),
        sa.Column('correlation_status', sa.String(length=20), nullable=False),
        sa.Column('credential_status', sa.String(length=30), nullable=True),
        sa.Column('credential_type', sa.String(length=30), nullable=True),
        sa.Column('jumpserver_reference', sa.String(length=255), nullable=True),
        sa.Column('correlation_error', sa.Text(), nullable=True),
        sa.Column('resource_group', sa.String(length=120), nullable=True),
        sa.Column('resource_version', sa.String(length=80), nullable=True),
        sa.Column('resource', sa.String(length=120), nullable=True),
        sa.Column('subresource', sa.String(length=120), nullable=True),
        sa.Column('resource_name', sa.String(length=253), nullable=True),
        sa.Column('kubernetes_namespace', sa.String(length=253), nullable=True),
        sa.Column('verb', sa.String(length=40), nullable=False),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=20), nullable=False),
        sa.Column('event_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('retention_class', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_kind IN ('kubernetes_audit')", name='ck_tenant_audit_evidence_source_kind'),
        sa.CheckConstraint(
            "principal_kind IN ('service_account', 'user', 'unknown')",
            name='ck_tenant_audit_evidence_principal_kind',
        ),
        sa.CheckConstraint(
            "identity_class IN ('human', 'admin', 'cicd', 'group', 'unmanaged', 'ambiguous')",
            name='ck_tenant_audit_evidence_identity_class',
        ),
        sa.CheckConstraint(
            "correlation_status IN ('matched', 'unmanaged', 'ambiguous')",
            name='ck_tenant_audit_evidence_correlation_status',
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'unknown')",
            name='ck_tenant_audit_evidence_outcome',
        ),
        sa.ForeignKeyConstraint(['access_grant_id'], ['tenant_access_grants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credential_id'], ['tenant_credentials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_audit_evidence_public_id'),
        sa.UniqueConstraint('cluster_id', 'idempotency_key', name='uq_tenant_audit_evidence_cluster_idempotency'),
    )
    op.create_index(
        'ix_tenant_audit_evidence_tenant_event',
        'tenant_audit_evidence',
        ['tenant_id', 'event_at'],
    )
    op.create_index(
        'ix_tenant_audit_evidence_namespace_event',
        'tenant_audit_evidence',
        ['tenant_namespace_id', 'event_at'],
    )
    op.create_index(
        'ix_tenant_audit_evidence_credential_event',
        'tenant_audit_evidence',
        ['credential_id', 'event_at'],
    )
    op.create_index(
        'ix_tenant_audit_evidence_correlation_event',
        'tenant_audit_evidence',
        ['correlation_status', 'event_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_tenant_audit_evidence_correlation_event', table_name='tenant_audit_evidence')
    op.drop_index('ix_tenant_audit_evidence_credential_event', table_name='tenant_audit_evidence')
    op.drop_index('ix_tenant_audit_evidence_namespace_event', table_name='tenant_audit_evidence')
    op.drop_index('ix_tenant_audit_evidence_tenant_event', table_name='tenant_audit_evidence')
    op.drop_table('tenant_audit_evidence')
