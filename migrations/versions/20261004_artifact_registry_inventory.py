"""add provider-neutral Artifact Registry inventory foundation

Revision ID: 20261004_registry_inventory
Revises: 20261003_registry_harbor
Create Date: 2026-10-04
"""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20261004_registry_inventory'
down_revision = '20261003_registry_harbor'
branch_labels = None
depends_on = None

PERMISSIONS = (
    (
        'artifact_registry.view',
        'artifact_registry',
        'view',
        'View committed Artifact Registry inventory, security, governance, runtime correlation, and analytics evidence.',
        'object_storage_inventory.view',
    ),
    (
        'artifact_registry.sync',
        'artifact_registry',
        'sync',
        'Run Artifact Registry reconciliation through canonical Job Execution.',
        'storage.sync',
    ),
)


def _ensure_permission(bind, permissions, *, key: str, module: str, action: str, description: str, now: datetime) -> int:
    permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == key)).scalar()
    if permission_id is None:
        bind.execute(
            permissions.insert().values(
                key=key,
                module=module,
                action=action,
                description=description,
                created_at=now,
            )
        )
        permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == key)).scalar_one()
    return int(permission_id)


def _copy_role_assignments(bind, permissions, role_permissions, *, source_key: str, target_id: int, now: datetime) -> None:
    source_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == source_key)).scalar()
    if source_id is None:
        return
    for row in bind.execute(
        sa.select(role_permissions.c.role_id).where(role_permissions.c.permission_id == source_id)
    ):
        exists = bind.execute(
            sa.select(role_permissions.c.role_id).where(
                role_permissions.c.role_id == row.role_id,
                role_permissions.c.permission_id == target_id,
            )
        ).scalar()
        if exists is None:
            bind.execute(
                role_permissions.insert().values(
                    role_id=row.role_id,
                    permission_id=target_id,
                    created_at=now,
                )
            )


def upgrade() -> None:
    op.create_table(
        'registry_collection_states',
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('last_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('counts', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('integration_instance_id'),
    )
    op.alter_column('registry_collection_states', 'status', server_default=None)

    op.create_table(
        'registry_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('public', sa.Boolean(), nullable=True),
        sa.Column('repository_count', sa.Integer(), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_instance_id', 'name', name='uq_registry_project_instance_name'),
    )
    op.create_index('ix_registry_projects_integration_instance_id', 'registry_projects', ['integration_instance_id'])
    op.create_index(
        'ix_registry_projects_instance_observed',
        'registry_projects',
        ['integration_instance_id', 'observed_at'],
    )

    op.create_table(
        'registry_repositories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('artifact_count', sa.Integer(), nullable=True),
        sa.Column('pull_count', sa.BigInteger(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('provider_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['registry_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_registry_repository_project_name'),
    )
    op.create_index('ix_registry_repositories_project_id', 'registry_repositories', ['project_id'])
    op.create_index(
        'ix_registry_repositories_project_observed',
        'registry_repositories',
        ['project_id', 'observed_at'],
    )

    op.create_table(
        'registry_artifacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repository_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('digest', sa.String(length=255), nullable=False),
        sa.Column('digest_algorithm', sa.String(length=32), nullable=False, server_default='unknown'),
        sa.Column('artifact_type', sa.String(length=120), nullable=True),
        sa.Column('media_type', sa.String(length=255), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('push_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pull_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['registry_repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'digest', name='uq_registry_artifact_repository_digest'),
    )
    op.alter_column('registry_artifacts', 'digest_algorithm', server_default=None)
    op.create_index('ix_registry_artifacts_repository_id', 'registry_artifacts', ['repository_id'])
    op.create_index('ix_registry_artifacts_digest', 'registry_artifacts', ['digest'])
    op.create_index(
        'ix_registry_artifacts_repository_observed',
        'registry_artifacts',
        ['repository_id', 'observed_at'],
    )

    op.create_table(
        'registry_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('push_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pull_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artifact_id'], ['registry_artifacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('artifact_id', 'name', name='uq_registry_tag_artifact_name'),
    )
    op.create_index('ix_registry_tags_artifact_id', 'registry_tags', ['artifact_id'])
    op.create_index('ix_registry_tags_name', 'registry_tags', ['name'])

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
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    for key, module, action, description, source_key in PERMISSIONS:
        target_id = _ensure_permission(
            bind,
            permissions,
            key=key,
            module=module,
            action=action,
            description=description,
            now=now,
        )
        _copy_role_assignments(
            bind,
            permissions,
            role_permissions,
            source_key=source_key,
            target_id=target_id,
            now=now,
        )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.Integer), sa.column('key', sa.String))
    role_permissions = sa.table('role_permissions', sa.column('permission_id', sa.Integer))
    permission_ids = [
        int(row.id)
        for row in bind.execute(
            sa.select(permissions.c.id).where(permissions.c.key.in_([item[0] for item in PERMISSIONS]))
        )
    ]
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
        bind.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))

    op.drop_index('ix_registry_tags_name', table_name='registry_tags')
    op.drop_index('ix_registry_tags_artifact_id', table_name='registry_tags')
    op.drop_table('registry_tags')
    op.drop_index('ix_registry_artifacts_repository_observed', table_name='registry_artifacts')
    op.drop_index('ix_registry_artifacts_digest', table_name='registry_artifacts')
    op.drop_index('ix_registry_artifacts_repository_id', table_name='registry_artifacts')
    op.drop_table('registry_artifacts')
    op.drop_index('ix_registry_repositories_project_observed', table_name='registry_repositories')
    op.drop_index('ix_registry_repositories_project_id', table_name='registry_repositories')
    op.drop_table('registry_repositories')
    op.drop_index('ix_registry_projects_instance_observed', table_name='registry_projects')
    op.drop_index('ix_registry_projects_integration_instance_id', table_name='registry_projects')
    op.drop_table('registry_projects')
    op.drop_table('registry_collection_states')
