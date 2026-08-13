"""Add object-storage bucket enrichment and optional usage statistics.

Revision ID: 20260813_obj_bucket_enrichment
Revises: 20260813_obj_asset_contract
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = '20260813_obj_bucket_enrichment'
down_revision = '20260813_obj_asset_contract'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('object_storage_buckets', sa.Column('size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('object_storage_buckets', sa.Column('object_count', sa.BigInteger(), nullable=True))
    op.add_column(
        'object_storage_buckets',
        sa.Column('usage_stats_state', sa.String(length=30), nullable=False, server_default='not_collected'),
    )
    op.add_column(
        'object_storage_buckets',
        sa.Column('usage_observed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('object_storage_buckets', 'usage_observed_at')
    op.drop_column('object_storage_buckets', 'usage_stats_state')
    op.drop_column('object_storage_buckets', 'object_count')
    op.drop_column('object_storage_buckets', 'size_bytes')
