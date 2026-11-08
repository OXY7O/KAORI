"""add storage policy to Tenant Resource Profiles and Namespace allocation snapshots

Revision ID: 20261001_profile_storage_policy
Revises: 20261001_profile_adv_controls
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = '20261001_profile_storage_policy'
down_revision = '20261001_profile_adv_controls'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_resource_profiles',
        sa.Column(
            'storage_policy_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column(
        'tenant_resource_profiles',
        'storage_policy_json',
        server_default=None,
    )
    op.add_column(
        'tenant_namespaces',
        sa.Column(
            'allocation_storage_policy_json',
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('tenant_namespaces', 'allocation_storage_policy_json')
    op.drop_column('tenant_resource_profiles', 'storage_policy_json')
