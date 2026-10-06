"""add Tenant production access governance

Revision ID: 20260926_tenant_prod_access
Revises: 20260926_tenant_deployer_cred
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = '20260926_tenant_prod_access'
down_revision = '20260926_tenant_deployer_cred'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_production_access_exceptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=False),
        sa.Column('access_grant_id', sa.Integer(), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('review_due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name='ck_tenant_production_access_exceptions_status',
        ),
        sa.CheckConstraint(
            'valid_from < valid_until',
            name='ck_tenant_production_access_exceptions_validity',
        ),
        sa.CheckConstraint(
            'review_due_at >= valid_from AND review_due_at <= valid_until',
            name='ck_tenant_production_access_exceptions_review_window',
        ),
        sa.ForeignKeyConstraint(['access_grant_id'], ['tenant_access_grants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'public_id',
            name='uq_tenant_production_access_exceptions_public_id',
        ),
        sa.UniqueConstraint(
            'correlation_id',
            name='uq_tenant_production_access_exceptions_correlation_id',
        ),
    )
    op.create_index(
        'ix_tenant_production_access_exceptions_scope_status',
        'tenant_production_access_exceptions',
        ['tenant_id', 'tenant_namespace_id', 'status'],
    )
    op.create_index(
        'ix_tenant_production_access_exceptions_owner_status',
        'tenant_production_access_exceptions',
        ['owner_user_id', 'status', 'valid_until'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_tenant_production_access_exceptions_owner_status',
        table_name='tenant_production_access_exceptions',
    )
    op.drop_index(
        'ix_tenant_production_access_exceptions_scope_status',
        table_name='tenant_production_access_exceptions',
    )
    op.drop_table('tenant_production_access_exceptions')
