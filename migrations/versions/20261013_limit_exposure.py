"""Add operator-governed CPU/Memory Limit Exposure policy.

Revision ID: 20261013_limit_exposure
Revises: 20261012_capsule_handback_guard
Create Date: 2026-10-13

Source-only until explicitly admitted through KAORI schema gates.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261013_limit_exposure'
down_revision = '20261012_capsule_handback_guard'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_capacity_policies',
        sa.Column('limit_exposure_mode', sa.String(length=16), nullable=False, server_default='observe'),
    )
    op.add_column(
        'tenant_capacity_policies',
        sa.Column('cpu_limit_ratio', sa.String(length=16), nullable=False, server_default='1.50'),
    )
    op.add_column(
        'tenant_capacity_policies',
        sa.Column('memory_limit_ratio', sa.String(length=16), nullable=False, server_default='1.00'),
    )
    op.create_check_constraint(
        'ck_tenant_capacity_limit_exposure_mode',
        'tenant_capacity_policies',
        "limit_exposure_mode IN ('observe', 'enforce')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_tenant_capacity_limit_exposure_mode', 'tenant_capacity_policies', type_='check')
    op.drop_column('tenant_capacity_policies', 'memory_limit_ratio')
    op.drop_column('tenant_capacity_policies', 'cpu_limit_ratio')
    op.drop_column('tenant_capacity_policies', 'limit_exposure_mode')
