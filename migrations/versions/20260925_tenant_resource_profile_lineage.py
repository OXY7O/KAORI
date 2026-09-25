"""add tenant Resource Profile base preset lineage

Revision ID: 20260925_tenant_profile_lineage
Revises: 20260925_tenant_allocations
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = '20260925_tenant_profile_lineage'
down_revision = '20260925_tenant_allocations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_resource_profiles',
        sa.Column('base_preset_class', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'tenant_resource_profiles',
        sa.Column('base_preset_version', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tenant_resource_profiles', 'base_preset_version')
    op.drop_column('tenant_resource_profiles', 'base_preset_class')
