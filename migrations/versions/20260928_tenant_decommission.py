"""add governed Tenant decommission lifecycle

Revision ID: 20260928_tenant_decommission
Revises: 20260927_tenant_capsule_adv
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op

revision = '20260928_tenant_decommission'
down_revision = '20260927_tenant_capsule_adv'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('generation', sa.Integer(), nullable=False, server_default='1'))
    op.create_check_constraint('ck_tenants_generation', 'tenants', 'generation >= 1')
    op.drop_constraint('uq_tenants_cluster_slug', 'tenants', type_='unique')
    op.create_unique_constraint(
        'uq_tenants_cluster_slug_generation',
        'tenants',
        ['cluster_id', 'slug', 'generation'],
    )

    op.drop_constraint(
        'ck_tenant_namespaces_provisioning_status',
        'tenant_namespaces',
        type_='check',
    )
    op.create_check_constraint(
        'ck_tenant_namespaces_provisioning_status',
        'tenant_namespaces',
        "provisioning_status IN ('pending', 'ready', 'drifted', 'failed', 'deprovisioning', 'deprovisioned')",
    )
    op.alter_column('tenants', 'generation', server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        'ck_tenant_namespaces_provisioning_status',
        'tenant_namespaces',
        type_='check',
    )
    op.create_check_constraint(
        'ck_tenant_namespaces_provisioning_status',
        'tenant_namespaces',
        "provisioning_status IN ('pending', 'ready', 'drifted', 'failed')",
    )

    op.drop_constraint('uq_tenants_cluster_slug_generation', 'tenants', type_='unique')
    op.create_unique_constraint('uq_tenants_cluster_slug', 'tenants', ['cluster_id', 'slug'])
    op.drop_constraint('ck_tenants_generation', 'tenants', type_='check')
    op.drop_column('tenants', 'generation')
