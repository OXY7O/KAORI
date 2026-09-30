"""add Extra Large Tenant Resource Profile class

Revision ID: 20260930_tenant_profile_xlarge
Revises: 20260928_tenant_namespace_gen
Create Date: 2026-09-30
"""

from alembic import op

revision = '20260930_tenant_profile_xlarge'
down_revision = '20260928_tenant_namespace_gen'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        'ck_tenant_resource_profiles_class',
        'tenant_resource_profiles',
        type_='check',
    )
    op.create_check_constraint(
        'ck_tenant_resource_profiles_class',
        'tenant_resource_profiles',
        "profile_class IN ('small', 'standard', 'large', 'extra_large', 'custom')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tenant_resource_profiles SET profile_class = 'large' "
        "WHERE profile_class = 'extra_large'"
    )
    op.drop_constraint(
        'ck_tenant_resource_profiles_class',
        'tenant_resource_profiles',
        type_='check',
    )
    op.create_check_constraint(
        'ck_tenant_resource_profiles_class',
        'tenant_resource_profiles',
        "profile_class IN ('small', 'standard', 'large', 'custom')",
    )
