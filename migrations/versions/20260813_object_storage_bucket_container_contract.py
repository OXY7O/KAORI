"""add provider-neutral bucket and container presentation contract

Revision ID: 20260813_obj_asset_contract
Revises: 20260813_inventory_op_names
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260813_obj_asset_contract'
down_revision = '20260813_inventory_op_names'
branch_labels = None
depends_on = None

_STATE_COLUMNS = (
    'versioning_state',
    'immutability_state',
    'encryption_state',
    'lifecycle_state',
    'replication_state',
    'access_policy_state',
    'exposure_state',
)


def upgrade() -> None:
    op.add_column(
        'object_storage_buckets',
        sa.Column('native_type', sa.String(length=32), nullable=False, server_default='bucket'),
    )
    op.add_column(
        'object_storage_buckets',
        sa.Column('location', sa.String(length=120), nullable=True),
    )
    for column_name in _STATE_COLUMNS:
        op.add_column(
            'object_storage_buckets',
            sa.Column(column_name, sa.String(length=30), nullable=False, server_default='not_collected'),
        )
    op.add_column(
        'object_storage_buckets',
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('object_storage_buckets', 'provider_metadata')
    for column_name in reversed(_STATE_COLUMNS):
        op.drop_column('object_storage_buckets', column_name)
    op.drop_column('object_storage_buckets', 'location')
    op.drop_column('object_storage_buckets', 'native_type')
