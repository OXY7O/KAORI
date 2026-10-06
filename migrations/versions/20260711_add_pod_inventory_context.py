"""add pod inventory runtime context

Revision ID: 20260711_pod_context
Revises: 20260711_namespace_context
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_pod_context'
down_revision: str | None = '20260711_namespace_context'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'pod_inventory',
        sa.Column(
            'details',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.alter_column(
        'pod_inventory',
        'details',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        'pod_inventory',
        'details',
    )
