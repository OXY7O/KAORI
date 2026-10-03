"""add Registry to Kubernetes runtime correlation

Revision ID: 20261004_registry_k8s_corr
Revises: 20261004_artifact_registry_sec
Create Date: 2026-10-04
"""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20261004_registry_k8s_corr'
down_revision = '20261004_artifact_registry_sec'
branch_labels = None
depends_on = None

PERMISSION = (
    'artifact_registry.runtime_correlation.view',
    'artifact_registry',
    'view_runtime_correlation',
    'View committed Artifact Registry to Kubernetes runtime correlation evidence.',
)


def upgrade() -> None:
    op.create_table(
        'registry_correlation_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_materialized'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('runtime_reference_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('digest_match_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tag_match_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ambiguous_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unmatched_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'registry_workload_bindings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('registry_artifact_id', sa.Integer(), nullable=True),
        sa.Column('pod_inventory_id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('pod_name', sa.String(length=255), nullable=False),
        sa.Column('workload_type', sa.String(length=50), nullable=True),
        sa.Column('workload_name', sa.String(length=255), nullable=True),
        sa.Column('container_kind', sa.String(length=30), nullable=False),
        sa.Column('container_name', sa.String(length=255), nullable=False),
        sa.Column('image_reference', sa.String(length=1000), nullable=False),
        sa.Column('image_id', sa.String(length=1000), nullable=False, server_default=''),
        sa.Column('registry_host', sa.String(length=255), nullable=True),
        sa.Column('repository_path', sa.String(length=700), nullable=True),
        sa.Column('tag', sa.String(length=255), nullable=True),
        sa.Column('digest', sa.String(length=255), nullable=True),
        sa.Column('match_type', sa.String(length=40), nullable=False),
        sa.Column('confidence', sa.String(length=30), nullable=False),
        sa.Column('candidate_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('registry_source_id', sa.Integer(), nullable=True),
        sa.Column('registry_provider_key', sa.String(length=80), nullable=True),
        sa.Column('registry_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('kubernetes_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('correlated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pod_inventory_id'], ['pod_inventory.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['registry_artifact_id'], ['registry_artifacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'pod_inventory_id',
            'container_kind',
            'container_name',
            'image_reference',
            'image_id',
            name='uq_registry_workload_binding_runtime_image',
        ),
    )
    op.create_index(
        'ix_registry_workload_bindings_registry_artifact_id',
        'registry_workload_bindings',
        ['registry_artifact_id'],
        unique=False,
    )
    op.create_index(
        'ix_registry_workload_bindings_pod_inventory_id',
        'registry_workload_bindings',
        ['pod_inventory_id'],
        unique=False,
    )
    op.create_index('ix_registry_workload_bindings_cluster_id', 'registry_workload_bindings', ['cluster_id'], unique=False)
    op.create_index('ix_registry_workload_bindings_namespace', 'registry_workload_bindings', ['namespace'], unique=False)
    op.create_index('ix_registry_workload_bindings_digest', 'registry_workload_bindings', ['digest'], unique=False)
    op.create_index(
        'ix_registry_workload_bindings_registry_source_id',
        'registry_workload_bindings',
        ['registry_source_id'],
        unique=False,
    )

    bind = op.get_bind()
    now = datetime.now(UTC)
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Integer),
        sa.column('key', sa.String),
        sa.column('module', sa.String),
        sa.column('action', sa.String),
        sa.column('description', sa.Text),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == PERMISSION[0])).scalar()
    if permission_id is None:
        bind.execute(
            permissions.insert().values(
                key=PERMISSION[0],
                module=PERMISSION[1],
                action=PERMISSION[2],
                description=PERMISSION[3],
                created_at=now,
            )
        )
        permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == PERMISSION[0])).scalar_one()

    roles = sa.table('roles', sa.column('id', sa.Integer), sa.column('name', sa.String))
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    for role_name in ('viewer', 'operator', 'editor', 'admin', 'auditor'):
        role_id = bind.execute(sa.select(roles.c.id).where(roles.c.name == role_name)).scalar()
        if role_id is None:
            continue
        exists = bind.execute(
            sa.select(role_permissions.c.role_id).where(
                role_permissions.c.role_id == role_id,
                role_permissions.c.permission_id == permission_id,
            )
        ).scalar()
        if exists is None:
            bind.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=permission_id,
                    created_at=now,
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.Integer), sa.column('key', sa.String))
    role_permissions = sa.table('role_permissions', sa.column('permission_id', sa.Integer))
    permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == PERMISSION[0])).scalar()
    if permission_id is not None:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id == permission_id))
        bind.execute(permissions.delete().where(permissions.c.id == permission_id))

    op.drop_index('ix_registry_workload_bindings_registry_source_id', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_digest', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_namespace', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_cluster_id', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_pod_inventory_id', table_name='registry_workload_bindings')
    op.drop_index('ix_registry_workload_bindings_registry_artifact_id', table_name='registry_workload_bindings')
    op.drop_table('registry_workload_bindings')
    op.drop_table('registry_correlation_states')
