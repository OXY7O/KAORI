"""add Artifact Registry runtime correlation

Revision ID: 20261004_registry_runtime
Revises: 20261004_registry_security
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20261004_registry_runtime'
down_revision = '20261004_registry_security'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'registry_workload_bindings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.Integer(), nullable=False),
        sa.Column('pod_inventory_id', sa.Integer(), nullable=False),
        sa.Column('image_reference', sa.String(length=2048), nullable=False),
        sa.Column('match_type', sa.String(length=30), nullable=False),
        sa.Column('confidence', sa.String(length=30), nullable=False),
        sa.Column('cluster_id', sa.String(length=255), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('workload_type', sa.String(length=50), nullable=True),
        sa.Column('workload_name', sa.String(length=255), nullable=True),
        sa.Column('pod_name', sa.String(length=255), nullable=False),
        sa.Column('container_name', sa.String(length=255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artifact_id'], ['registry_artifacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pod_inventory_id'], ['pod_inventory.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'artifact_id',
            'pod_inventory_id',
            'image_reference',
            name='uq_registry_workload_binding_identity',
        ),
    )
    op.create_index('ix_registry_workload_bindings_artifact_id', 'registry_workload_bindings', ['artifact_id'])
    op.create_index(
        'ix_registry_workload_bindings_pod_inventory_id', 'registry_workload_bindings', ['pod_inventory_id']
    )
    op.create_index('ix_registry_workload_bindings_cluster_id', 'registry_workload_bindings', ['cluster_id'])
    op.create_index(
        'ix_registry_workload_bindings_cluster_namespace',
        'registry_workload_bindings',
        ['cluster_id', 'namespace'],
    )
    op.create_index(
        'ix_registry_workload_bindings_artifact_observed',
        'registry_workload_bindings',
        ['artifact_id', 'observed_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_registry_workload_bindings_artifact_observed', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_cluster_namespace', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_cluster_id', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_pod_inventory_id', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_artifact_id', table_name='registry_workload_bindings')
    op.drop_table('registry_workload_bindings')
