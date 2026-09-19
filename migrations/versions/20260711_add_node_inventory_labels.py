"""add Kubernetes labels to node inventory

Revision ID: 20260711_node_labels
Revises: 20260711_node_conditions
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_node_labels'
down_revision: str | None = '20260711_node_conditions'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column(
            'labels',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.alter_column(
        'node_inventory',
        'labels',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        'node_inventory',
        'labels',
    )
