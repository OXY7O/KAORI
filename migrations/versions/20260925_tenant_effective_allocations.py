"""add tenant effective allocation snapshots

Revision ID: 20260925_tenant_allocations
Revises: 20260925_tenant_profiles
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = '20260925_tenant_allocations'
down_revision = '20260925_tenant_profiles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_resource_profiles',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'tenant_namespaces',
        sa.Column('resource_profile_version', sa.Integer(), nullable=True),
    )
    op.add_column(
        'tenant_namespaces',
        sa.Column('allocation_quota_json', sa.JSON(), nullable=True),
    )
    op.add_column(
        'tenant_namespaces',
        sa.Column('allocation_limit_defaults_json', sa.JSON(), nullable=True),
    )
    op.add_column(
        'tenant_namespaces',
        sa.Column('allocation_customized', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('tenant_resource_profiles', 'version', server_default=None)
    op.alter_column('tenant_namespaces', 'allocation_customized', server_default=None)


def downgrade() -> None:
    op.drop_column('tenant_namespaces', 'allocation_customized')
    op.drop_column('tenant_namespaces', 'allocation_limit_defaults_json')
    op.drop_column('tenant_namespaces', 'allocation_quota_json')
    op.drop_column('tenant_namespaces', 'resource_profile_version')
    op.drop_column('tenant_resource_profiles', 'version')
