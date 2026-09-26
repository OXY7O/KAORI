"""add Tenant human and administrator credential lifecycle

Revision ID: 20260926_tenant_credentials
Revises: 20260926_tenant_access
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = '20260926_tenant_credentials'
down_revision = '20260926_tenant_access'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=False),
        sa.Column('access_grant_id', sa.Integer(), nullable=True),
        sa.Column('anchor_namespace_id', sa.Integer(), nullable=True),
        sa.Column('credential_type', sa.String(length=30), nullable=False),
        sa.Column('purpose', sa.String(length=120), nullable=False),
        sa.Column('delivery_method', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('reconciliation_status', sa.String(length=30), nullable=False),
        sa.Column('service_account_name', sa.String(length=63), nullable=False),
        sa.Column('jumpserver_reference', sa.String(length=255), nullable=True),
        sa.Column('exception_authorized_by_user_id', sa.Integer(), nullable=True),
        sa.Column('exception_reason', sa.Text(), nullable=True),
        sa.Column('exception_valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('renewal_due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
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
            "credential_type IN ('human_service_account', 'admin_kubeconfig')",
            name='ck_tenant_credentials_type',
        ),
        sa.CheckConstraint(
            "delivery_method IN ('jumpserver', 'exceptional_kubeconfig', 'admin_kubeconfig')",
            name='ck_tenant_credentials_delivery_method',
        ),
        sa.CheckConstraint(
            "status IN ('active', 'renewal_due', 'rotating', 'suspended', 'expired', 'revoked')",
            name='ck_tenant_credentials_status',
        ),
        sa.CheckConstraint(
            "reconciliation_status IN ('pending', 'ready', 'drifted', 'failed', 'disabled')",
            name='ck_tenant_credentials_reconciliation_status',
        ),
        sa.CheckConstraint(
            "((credential_type = 'human_service_account' AND access_grant_id IS NOT NULL "
            'AND anchor_namespace_id IS NULL '
            "AND delivery_method IN ('jumpserver', 'exceptional_kubeconfig')) "
            "OR (credential_type = 'admin_kubeconfig' AND access_grant_id IS NULL "
            "AND anchor_namespace_id IS NOT NULL AND delivery_method = 'admin_kubeconfig'))",
            name='ck_tenant_credentials_type_scope',
        ),
        sa.CheckConstraint(
            "(delivery_method != 'exceptional_kubeconfig' "
            'OR (exception_authorized_by_user_id IS NOT NULL AND exception_reason IS NOT NULL '
            'AND exception_valid_until IS NOT NULL))',
            name='ck_tenant_credentials_exception_approval',
        ),
        sa.CheckConstraint('rotation_generation >= 1', name='ck_tenant_credentials_generation'),
        sa.CheckConstraint('valid_from < valid_until', name='ck_tenant_credentials_validity'),
        sa.CheckConstraint(
            'renewal_due_at >= valid_from AND renewal_due_at <= valid_until',
            name='ck_tenant_credentials_renewal_window',
        ),
        sa.ForeignKeyConstraint(['access_grant_id'], ['tenant_access_grants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['anchor_namespace_id'], ['tenant_namespaces.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(
            ['exception_authorized_by_user_id'],
            ['users.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_credentials_public_id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_credentials_correlation_id'),
        sa.UniqueConstraint(
            'tenant_id',
            'owner_user_id',
            'credential_type',
            'purpose',
            name='uq_tenant_credentials_owner_purpose',
        ),
        sa.UniqueConstraint(
            'tenant_id',
            'service_account_name',
            name='uq_tenant_credentials_service_account_name',
        ),
    )
    op.create_index(
        'ix_tenant_credentials_tenant_status',
        'tenant_credentials',
        ['tenant_id', 'status'],
    )
    op.create_index(
        'ix_tenant_credentials_owner_status',
        'tenant_credentials',
        ['owner_user_id', 'status'],
    )
    op.create_index(
        'ix_tenant_credentials_validity',
        'tenant_credentials',
        ['status', 'renewal_due_at', 'valid_until'],
    )
    op.create_index(
        'ix_tenant_credentials_reconciliation',
        'tenant_credentials',
        ['tenant_id', 'reconciliation_status'],
    )

    op.create_table(
        'tenant_credential_generations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('credential_id', sa.Integer(), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('provider_evidence_json', sa.JSON(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.CheckConstraint('generation >= 1', name='ck_tenant_credential_generations_generation'),
        sa.ForeignKeyConstraint(['credential_id'], ['tenant_credentials.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'credential_id',
            'generation',
            name='uq_tenant_credential_generations_generation',
        ),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_credential_generations_correlation_id'),
    )
    op.create_index(
        'ix_tenant_credential_generations_credential',
        'tenant_credential_generations',
        ['credential_id', 'generation'],
    )


def downgrade() -> None:
    op.drop_index('ix_tenant_credential_generations_credential', table_name='tenant_credential_generations')
    op.drop_table('tenant_credential_generations')
    op.drop_index('ix_tenant_credentials_reconciliation', table_name='tenant_credentials')
    op.drop_index('ix_tenant_credentials_validity', table_name='tenant_credentials')
    op.drop_index('ix_tenant_credentials_owner_status', table_name='tenant_credentials')
    op.drop_index('ix_tenant_credentials_tenant_status', table_name='tenant_credentials')
    op.drop_table('tenant_credentials')
