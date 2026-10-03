"""add advanced controls to Tenant Resource Profiles

Revision ID: 20261001_profile_adv_controls
Revises: 20260930_tenant_profile_xlarge
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = '20261001_profile_adv_controls'
down_revision = '20260930_tenant_profile_xlarge'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_resource_profiles',
        sa.Column(
            'advanced_controls_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column(
        'tenant_resource_profiles',
        'advanced_controls_json',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column('tenant_resource_profiles', 'advanced_controls_json')
