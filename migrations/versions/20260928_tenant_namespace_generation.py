"""allow governed namespace reuse after verified deprovision

Revision ID: 20260928_tenant_namespace_gen
Revises: 20260928_tenant_decommission
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op

revision = '20260928_tenant_namespace_gen'
down_revision = '20260928_tenant_decommission'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_namespaces',
        sa.Column('generation', sa.Integer(), nullable=False, server_default='1'),
    )
    op.create_check_constraint(
        'ck_tenant_namespaces_generation',
        'tenant_namespaces',
        'generation >= 1',
    )
    op.drop_constraint(
        'uq_tenant_namespaces_cluster_namespace',
        'tenant_namespaces',
        type_='unique',
    )
    op.create_unique_constraint(
        'uq_tenant_namespaces_cluster_namespace_generation',
        'tenant_namespaces',
        ['cluster_id', 'namespace', 'generation'],
    )
    op.alter_column('tenant_namespaces', 'generation', server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        'uq_tenant_namespaces_cluster_namespace_generation',
        'tenant_namespaces',
        type_='unique',
    )
    op.create_unique_constraint(
        'uq_tenant_namespaces_cluster_namespace',
        'tenant_namespaces',
        ['cluster_id', 'namespace'],
    )
    op.drop_constraint(
        'ck_tenant_namespaces_generation',
        'tenant_namespaces',
        type_='check',
    )
    op.drop_column('tenant_namespaces', 'generation')
