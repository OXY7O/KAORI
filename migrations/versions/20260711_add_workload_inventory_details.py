"""add workload inventory details metadata

Revision ID: 20260711_workload_details
Revises: 20260711_inventory_enrichment
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_workload_details'
down_revision: str | None = '20260711_inventory_enrichment'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'workload_inventory',
        sa.Column(
            'details',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column(
        'workload_inventory',
        'details',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        'workload_inventory',
        'details',
    )
