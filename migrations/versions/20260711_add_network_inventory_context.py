"""add service and ingress inventory context

Revision ID: 20260711_network_context
Revises: 20260711_pod_context
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_network_context'
down_revision: str | None = '20260711_pod_context'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'service_inventory',
        sa.Column(
            'details',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.alter_column(
        'service_inventory',
        'details',
        server_default=None,
    )

    op.add_column(
        'ingress_inventory',
        sa.Column(
            'details',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.alter_column(
        'ingress_inventory',
        'details',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column('ingress_inventory', 'details')
    op.drop_column('service_inventory', 'details')
