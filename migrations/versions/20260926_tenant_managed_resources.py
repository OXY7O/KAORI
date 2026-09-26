"""add Tenant managed TLS and registry resource intents

Revision ID: 20260926_tenant_managed_res
Revises: 20260926_tenant_prod_access
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = '20260926_tenant_managed_res'
down_revision = '20260926_tenant_prod_access'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_managed_resource_intents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=False),
        sa.Column('resource_kind', sa.String(length=20), nullable=False),
        sa.Column('mode', sa.String(length=40), nullable=False),
        sa.Column('resource_name', sa.String(length=253), nullable=False),
        sa.Column('source_reference', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('rotation_generation', sa.Integer(), nullable=False),
        sa.Column('desired_hash', sa.String(length=64), nullable=True),
        sa.Column('effective_hash', sa.String(length=64), nullable=True),
        sa.Column('reconciliation_message', sa.Text(), nullable=True),
        sa.Column('reconciliation_evidence_json', sa.JSON(), nullable=True),
        sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resource_kind IN ('tls', 'registry')",
            name='ck_tenant_managed_resource_intents_kind',
        ),
        sa.CheckConstraint(
            "mode IN ('platform_tls', 'namespace_tls_compat', 'image_pull_secret', 'external_credential_provider')",
            name='ck_tenant_managed_resource_intents_mode',
        ),
        sa.CheckConstraint(
            "((resource_kind = 'tls' AND mode IN ('platform_tls', 'namespace_tls_compat')) "
            "OR (resource_kind = 'registry' AND mode IN ('image_pull_secret', 'external_credential_provider')))",
            name='ck_tenant_managed_resource_intents_kind_mode',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'drifted', 'failed', 'disabled')",
            name='ck_tenant_managed_resource_intents_status',
        ),
        sa.CheckConstraint(
            'rotation_generation >= 1',
            name='ck_tenant_managed_resource_intents_generation',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'public_id',
            name='uq_tenant_managed_resource_intents_public_id',
        ),
        sa.UniqueConstraint(
            'correlation_id',
            name='uq_tenant_managed_resource_intents_correlation_id',
        ),
        sa.UniqueConstraint(
            'tenant_namespace_id',
            'resource_kind',
            name='uq_tenant_managed_resource_intents_namespace_kind',
        ),
    )
    op.create_index(
        'ix_tenant_managed_resource_intents_tenant_status',
        'tenant_managed_resource_intents',
        ['tenant_id', 'status'],
    )
    op.create_index(
        'ix_tenant_managed_resource_intents_namespace',
        'tenant_managed_resource_intents',
        ['tenant_namespace_id', 'resource_kind'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_tenant_managed_resource_intents_namespace',
        table_name='tenant_managed_resource_intents',
    )
    op.drop_index(
        'ix_tenant_managed_resource_intents_tenant_status',
        table_name='tenant_managed_resource_intents',
    )
    op.drop_table('tenant_managed_resource_intents')
