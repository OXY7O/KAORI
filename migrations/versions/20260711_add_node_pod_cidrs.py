"""add node pod cidr inventory metadata

Revision ID: 20260711_node_pod_cidrs
Revises: 20260711_workload_details
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_node_pod_cidrs'
down_revision: str | None = '20260711_workload_details'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column(
            'pod_cidrs',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.alter_column(
        'node_inventory',
        'pod_cidrs',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        'node_inventory',
        'pod_cidrs',
    )
