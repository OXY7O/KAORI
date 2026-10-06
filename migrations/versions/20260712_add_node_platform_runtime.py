"""add node platform and runtime metadata

Revision ID: 20260712_node_platform
Revises: 20260711_network_context
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260712_node_platform'
down_revision: str | None = '20260711_network_context'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column('operating_system', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('architecture', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('kubelet_version', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'node_inventory',
        sa.Column('kube_proxy_version', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('node_inventory', 'kube_proxy_version')
    op.drop_column('node_inventory', 'kubelet_version')
    op.drop_column('node_inventory', 'architecture')
    op.drop_column('node_inventory', 'operating_system')
