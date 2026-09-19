"""add namespace metadata, controls, and security context

Revision ID: 20260711_namespace_context
Revises: 20260711_node_created_at
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_namespace_context'
down_revision: str | None = '20260711_node_created_at'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'namespace_inventory',
        sa.Column('uid', sa.String(length=128), nullable=True),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column(
            'labels',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column(
            'annotations',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column('limit_range_count', sa.Integer(), nullable=True),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column('network_policy_count', sa.Integer(), nullable=True),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column('service_account_count', sa.Integer(), nullable=True),
    )
    op.add_column(
        'namespace_inventory',
        sa.Column('default_service_account_present', sa.Boolean(), nullable=True),
    )

    op.alter_column(
        'namespace_inventory',
        'labels',
        server_default=None,
    )
    op.alter_column(
        'namespace_inventory',
        'annotations',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column('namespace_inventory', 'default_service_account_present')
    op.drop_column('namespace_inventory', 'service_account_count')
    op.drop_column('namespace_inventory', 'network_policy_count')
    op.drop_column('namespace_inventory', 'limit_range_count')
    op.drop_column('namespace_inventory', 'annotations')
    op.drop_column('namespace_inventory', 'labels')
    op.drop_column('namespace_inventory', 'created_at')
    op.drop_column('namespace_inventory', 'uid')
