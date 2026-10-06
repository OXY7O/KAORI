"""Add canonical object-storage bucket quota evidence.

Revision ID: 20260813_obj_bucket_quota
Revises: 20260813_obj_bucket_enrichment
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = '20260813_obj_bucket_quota'
down_revision = '20260813_obj_bucket_enrichment'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('object_storage_buckets', sa.Column('quota_bytes', sa.BigInteger(), nullable=True))
    op.add_column(
        'object_storage_buckets',
        sa.Column('quota_state', sa.String(length=30), nullable=False, server_default='not_collected'),
    )
    op.add_column(
        'object_storage_buckets',
        sa.Column('quota_observed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('object_storage_buckets', 'quota_observed_at')
    op.drop_column('object_storage_buckets', 'quota_state')
    op.drop_column('object_storage_buckets', 'quota_bytes')
