"""add Tenant membership and access grant governance

Revision ID: 20260926_tenant_access
Revises: 20260925_tenant_capacity
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = '20260926_tenant_access'
down_revision = '20260925_tenant_capacity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('subject_name', sa.String(length=253), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_groups_public_id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_groups_correlation_id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_tenant_groups_tenant_slug'),
    )
    op.create_index('ix_tenant_groups_tenant_enabled', 'tenant_groups', ['tenant_id', 'enabled'])

    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('principal_type', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('subject_name', sa.String(length=253), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("principal_type IN ('user', 'group')", name='ck_tenant_memberships_principal_type'),
        sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_tenant_memberships_status'),
        sa.CheckConstraint(
            "((principal_type = 'user' AND user_id IS NOT NULL AND group_id IS NULL) "
            "OR (principal_type = 'group' AND group_id IS NOT NULL AND user_id IS NULL))",
            name='ck_tenant_memberships_principal_reference',
        ),
        sa.ForeignKeyConstraint(['group_id'], ['tenant_groups.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_memberships_correlation_id'),
        sa.UniqueConstraint('tenant_id', 'group_id', name='uq_tenant_memberships_tenant_group'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_memberships_tenant_user'),
    )
    op.create_index('ix_tenant_memberships_tenant_status', 'tenant_memberships', ['tenant_id', 'status'])

    op.create_table(
        'tenant_access_grants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=True),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=True),
        sa.Column('scope_type', sa.String(length=20), nullable=False),
        sa.Column('access_profile', sa.String(length=30), nullable=False),
        sa.Column('access_profile_version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reconciliation_status', sa.String(length=30), nullable=False),
        sa.Column('reconciliation_message', sa.Text(), nullable=True),
        sa.Column('desired_hash', sa.String(length=64), nullable=True),
        sa.Column('effective_hash', sa.String(length=64), nullable=True),
        sa.Column('reconciliation_evidence_json', sa.JSON(), nullable=True),
        sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('tenant', 'environment', 'namespace')",
            name='ck_tenant_access_grants_scope_type',
        ),
        sa.CheckConstraint(
            "access_profile IN ('viewer', 'operator', 'tenant_admin', 'deployer')",
            name='ck_tenant_access_grants_profile',
        ),
        sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_tenant_access_grants_status'),
        sa.CheckConstraint(
            "reconciliation_status IN ('pending', 'ready', 'drifted', 'failed', 'revoked')",
            name='ck_tenant_access_grants_reconciliation_status',
        ),
        sa.CheckConstraint(
            "((scope_type = 'tenant' AND tenant_environment_id IS NULL AND tenant_namespace_id IS NULL) "
            "OR (scope_type = 'environment' AND tenant_environment_id IS NOT NULL AND tenant_namespace_id IS NULL) "
            "OR (scope_type = 'namespace' AND tenant_environment_id IS NULL AND tenant_namespace_id IS NOT NULL))",
            name='ck_tenant_access_grants_scope_reference',
        ),
        sa.ForeignKeyConstraint(['membership_id'], ['tenant_memberships.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_access_grants_public_id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_access_grants_correlation_id'),
    )
    op.create_index(
        'ix_tenant_access_grants_tenant_status',
        'tenant_access_grants',
        ['tenant_id', 'status'],
    )
    op.create_index(
        'ix_tenant_access_grants_membership',
        'tenant_access_grants',
        ['membership_id', 'scope_type'],
    )
    op.create_index(
        'ix_tenant_access_grants_reconciliation',
        'tenant_access_grants',
        ['tenant_id', 'reconciliation_status'],
    )


def downgrade() -> None:
    op.drop_index('ix_tenant_access_grants_reconciliation', table_name='tenant_access_grants')
    op.drop_index('ix_tenant_access_grants_membership', table_name='tenant_access_grants')
    op.drop_index('ix_tenant_access_grants_tenant_status', table_name='tenant_access_grants')
    op.drop_table('tenant_access_grants')
    op.drop_index('ix_tenant_memberships_tenant_status', table_name='tenant_memberships')
    op.drop_table('tenant_memberships')
    op.drop_index('ix_tenant_groups_tenant_enabled', table_name='tenant_groups')
    op.drop_table('tenant_groups')
