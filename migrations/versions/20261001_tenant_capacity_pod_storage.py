"""extend Tenant capacity governance to Pods and logical storage budget

Revision ID: 20261001_tenant_capacity_pod_storage
Revises: 20261001_profile_storage_policy
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = '20261001_tenant_capacity_pod_storage'
down_revision = '20261001_profile_storage_policy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_capacity_policies',
        sa.Column('platform_reserve_pods', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'tenant_capacity_policies',
        sa.Column('unmanaged_commitment_pods', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'tenant_capacity_policies',
        sa.Column('tenant_storage_budget', sa.String(length=50), nullable=True),
    )
    op.alter_column('tenant_capacity_policies', 'platform_reserve_pods', server_default=None)
    op.alter_column('tenant_capacity_policies', 'unmanaged_commitment_pods', server_default=None)


def downgrade() -> None:
    op.drop_column('tenant_capacity_policies', 'tenant_storage_budget')
    op.drop_column('tenant_capacity_policies', 'unmanaged_commitment_pods')
    op.drop_column('tenant_capacity_policies', 'platform_reserve_pods')
