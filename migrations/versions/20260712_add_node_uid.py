"""add Kubernetes node UID to inventory

Revision ID: 20260712_node_uid
Revises: 20260712_node_platform
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260712_node_uid'
down_revision: str | None = '20260712_node_platform'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'node_inventory',
        sa.Column('node_uid', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('node_inventory', 'node_uid')
