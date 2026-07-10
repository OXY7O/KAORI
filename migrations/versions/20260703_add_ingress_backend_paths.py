"""add ingress backend paths

Revision ID: 20260703_add_ingress_paths
Revises: 20260702_add_pod_images
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = '20260703_add_ingress_paths'
down_revision = '20260702_add_pod_images'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ingress_inventory',
        sa.Column(
            'backend_paths',
            sa.JSON(),
            nullable=False,
            server_default='[]',
        ),
    )


def downgrade() -> None:
    op.drop_column(
        'ingress_inventory',
        'backend_paths',
    )
