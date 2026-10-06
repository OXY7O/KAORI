"""add inventory relationships, configuration objects, and resource quotas

Revision ID: 20260711_inventory_enrichment
Revises: 20260711_user_timezone
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260711_inventory_enrichment'
down_revision: str | None = '20260711_user_timezone'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'pod_inventory',
        sa.Column('labels', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        'pod_inventory',
        sa.Column('container_names', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column('pod_inventory', sa.Column('workload_type', sa.String(length=50), nullable=True))
    op.add_column('pod_inventory', sa.Column('workload_name', sa.String(length=255), nullable=True))
    op.add_column(
        'pod_inventory',
        sa.Column('configuration_references', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        'pod_inventory',
        sa.Column('persistent_volume_claims', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    op.add_column(
        'service_inventory',
        sa.Column('selector', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.add_column(
        'storage_inventory',
        sa.Column('details', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        'configuration_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('object_type', sa.String(length=50), nullable=False),
        sa.Column('secret_type', sa.String(length=255), nullable=True),
        sa.Column('key_names', sa.JSON(), nullable=False),
        sa.Column('key_count', sa.Integer(), nullable=False),
        sa.Column('immutable', sa.Boolean(), nullable=False),
        sa.Column('payload_size_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            'object_type',
            name='uq_configuration_inventory_object',
        ),
    )
    op.create_index(
        'ix_configuration_inventory_cluster_id',
        'configuration_inventory',
        ['cluster_id'],
        unique=False,
    )
    op.create_index(
        'ix_configuration_inventory_namespace',
        'configuration_inventory',
        ['namespace'],
        unique=False,
    )
    op.create_index(
        'ix_configuration_inventory_object_type',
        'configuration_inventory',
        ['object_type'],
        unique=False,
    )

    op.create_table(
        'resource_quota_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('hard', sa.JSON(), nullable=False),
        sa.Column('used', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            name='uq_resource_quota_inventory_object',
        ),
    )
    op.create_index(
        'ix_resource_quota_inventory_cluster_id',
        'resource_quota_inventory',
        ['cluster_id'],
        unique=False,
    )
    op.create_index(
        'ix_resource_quota_inventory_namespace',
        'resource_quota_inventory',
        ['namespace'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_resource_quota_inventory_namespace', table_name='resource_quota_inventory')
    op.drop_index('ix_resource_quota_inventory_cluster_id', table_name='resource_quota_inventory')
    op.drop_table('resource_quota_inventory')

    op.drop_index('ix_configuration_inventory_object_type', table_name='configuration_inventory')
    op.drop_index('ix_configuration_inventory_namespace', table_name='configuration_inventory')
    op.drop_index('ix_configuration_inventory_cluster_id', table_name='configuration_inventory')
    op.drop_table('configuration_inventory')

    op.drop_column('storage_inventory', 'details')
    op.drop_column('service_inventory', 'selector')
    op.drop_column('pod_inventory', 'persistent_volume_claims')
    op.drop_column('pod_inventory', 'configuration_references')
    op.drop_column('pod_inventory', 'workload_name')
    op.drop_column('pod_inventory', 'workload_type')
    op.drop_column('pod_inventory', 'container_names')
    op.drop_column('pod_inventory', 'labels')
