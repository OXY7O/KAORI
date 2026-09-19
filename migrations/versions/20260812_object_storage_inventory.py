"""add committed object storage bucket inventory

Revision ID: 20260812_obj_storage_inv
Revises: 20260812_minio_owner_cleanup
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260812_obj_storage_inv'
down_revision = '20260812_minio_owner_cleanup'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'object_storage_systems',
        sa.Column('inventory_observed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'object_storage_buckets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_storage_system_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('provider_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['object_storage_system_id'],
            ['object_storage_systems.id'],
            name='fk_object_storage_buckets_system',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'object_storage_system_id',
            'name',
            name='uq_object_storage_bucket_system_name',
        ),
    )
    op.create_index(
        'ix_object_storage_buckets_object_storage_system_id',
        'object_storage_buckets',
        ['object_storage_system_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_object_storage_buckets_object_storage_system_id', table_name='object_storage_buckets')
    op.drop_table('object_storage_buckets')
    op.drop_column('object_storage_systems', 'inventory_observed_at')
