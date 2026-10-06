"""add advanced Capsule Tenant capability intents

Revision ID: 20260927_tenant_capsule_adv
Revises: 20260927_tenant_audit_corr
Create Date: 2026-09-27
"""

import sqlalchemy as sa
from alembic import op

revision = '20260927_tenant_capsule_adv'
down_revision = '20260927_tenant_audit_corr'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_advanced_capability_intents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=True),
        sa.Column('provider_key', sa.String(length=40), nullable=False),
        sa.Column('capability_key', sa.String(length=80), nullable=False),
        sa.Column('resource_kind', sa.String(length=80), nullable=False),
        sa.Column('resource_name', sa.String(length=253), nullable=False),
        sa.Column('provider_api_version', sa.String(length=40), nullable=False),
        sa.Column('desired_spec_json', sa.JSON(), nullable=False),
        sa.Column('effective_spec_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('desired_hash', sa.String(length=64), nullable=True),
        sa.Column('effective_hash', sa.String(length=64), nullable=True),
        sa.Column('reconciliation_message', sa.Text(), nullable=True),
        sa.Column('reconciliation_evidence_json', sa.JSON(), nullable=True),
        sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider_key IN ('capsule')", name='ck_tenant_advanced_capability_intents_provider'),
        sa.CheckConstraint(
            "resource_kind IN ('global_resource_quota', 'resource_pool', 'resource_pool_claim', "
            "'tenant_resource', 'global_tenant_resource', 'tenant_cordon', 'namespace_controls', "
            "'resource_rules', 'cross_namespace_credential')",
            name='ck_tenant_advanced_capability_intents_kind',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'drifted', 'failed', 'disabled')",
            name='ck_tenant_advanced_capability_intents_status',
        ),
        sa.CheckConstraint('generation >= 1', name='ck_tenant_advanced_capability_intents_generation'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_advanced_capability_intents_public_id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_advanced_capability_intents_correlation_id'),
    )
    op.create_index(
        'ix_tenant_advanced_capability_intents_tenant_status',
        'tenant_advanced_capability_intents',
        ['tenant_id', 'status'],
    )
    op.create_index(
        'ix_tenant_advanced_capability_intents_capability',
        'tenant_advanced_capability_intents',
        ['tenant_id', 'capability_key', 'resource_kind'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_tenant_advanced_capability_intents_capability',
        table_name='tenant_advanced_capability_intents',
    )
    op.drop_index(
        'ix_tenant_advanced_capability_intents_tenant_status',
        table_name='tenant_advanced_capability_intents',
    )
    op.drop_table('tenant_advanced_capability_intents')
