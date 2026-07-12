"""add Kubernetes node system UUID to inventory

Revision ID: 20260712_node_system_uuid
Revises: 20260712_node_uid
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260712_node_system_uuid'
down_revision: str | None = '20260712_node_uid'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column('system_uuid', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('node_inventory', 'system_uuid')
