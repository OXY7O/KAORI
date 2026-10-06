"""Add Kubernetes creation timestamp to node inventory.

Revision ID: 20260711_node_created_at
Revises: 20260711_node_labels
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision: str = '20260711_node_created_at'
down_revision: str | None = '20260711_node_labels'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        'node_inventory',
        'created_at',
    )
