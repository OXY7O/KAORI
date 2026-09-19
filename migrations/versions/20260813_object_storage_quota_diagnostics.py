"""Add object-storage quota diagnostic evidence.

Revision ID: 20260813_obj_quota_diag
Revises: 20260813_obj_bucket_quota
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = '20260813_obj_quota_diag'
down_revision = '20260813_obj_bucket_quota'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'object_storage_buckets',
        sa.Column('quota_source', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'object_storage_buckets',
        sa.Column(
            'quota_evidence_code',
            sa.String(length=50),
            nullable=False,
            server_default='not_collected',
        ),
    )
    op.add_column(
        'object_storage_buckets',
        sa.Column('quota_checked_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('object_storage_buckets', 'quota_checked_at')
    op.drop_column('object_storage_buckets', 'quota_evidence_code')
    op.drop_column('object_storage_buckets', 'quota_source')
