"""add pod inventory images

Revision ID: 20260702_add_pod_images
Revises: 
Create Date: 2026-07-02

"""

from alembic import op
import sqlalchemy as sa


revision = '20260702_add_pod_images'
down_revision = '80ecb7191df4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'pod_inventory',
        sa.Column(
            'container_images',
            sa.JSON(),
            nullable=False,
            server_default='[]',
        ),
    )
    op.add_column(
        'pod_inventory',
        sa.Column(
            'init_container_images',
            sa.JSON(),
            nullable=False,
            server_default='[]',
        ),
    )
    op.add_column(
        'pod_inventory',
        sa.Column(
            'image_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade():
    op.drop_column(
        'pod_inventory',
        'image_count',
    )
    op.drop_column(
        'pod_inventory',
        'init_container_images',
    )
    op.drop_column(
        'pod_inventory',
        'container_images',
    )
