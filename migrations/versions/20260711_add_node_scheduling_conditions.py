"""add node scheduling and condition inventory

Revision ID: 20260711_node_conditions
Revises: 20260711_remove_node_pod_cidrs
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_node_conditions'
down_revision: str | None = '20260711_remove_node_pod_cidrs'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column('unschedulable', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('memory_pressure', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('disk_pressure', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('pid_pressure', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('network_unavailable', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('taints', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('node_inventory', 'taints')
    op.drop_column('node_inventory', 'network_unavailable')
    op.drop_column('node_inventory', 'pid_pressure')
    op.drop_column('node_inventory', 'disk_pressure')
    op.drop_column('node_inventory', 'memory_pressure')
    op.drop_column('node_inventory', 'unschedulable')
