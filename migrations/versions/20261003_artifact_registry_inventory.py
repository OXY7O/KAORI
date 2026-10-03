"""add provider-neutral Artifact Registry committed inventory

Revision ID: 20261003_artifact_registry_inv
Revises: 20261003_registry_harbor
Create Date: 2026-10-03
"""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20261003_artifact_registry_inv'
down_revision = '20261003_registry_harbor'
branch_labels = None
depends_on = None

VIEW_PERMISSION = (
    'artifact_registry.view',
    'artifact_registry',
    'view',
    'View committed Artifact Registry inventory and provider provenance.',
)
SYNC_PERMISSION = (
    'artifact_registry.sync',
    'artifact_registry',
    'sync',
    'Run Artifact Registry inventory synchronization through canonical Job Execution.',
)


def _ensure_permission(bind, permissions, permission, now: datetime) -> int:
    key, module, action, description = permission
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


def _grant(bind, *, permission_id: int, role_names: tuple[str, ...], now: datetime) -> None:
    roles = sa.table('roles', sa.column('id', sa.Integer), sa.column('name', sa.String))
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    for role_name in role_names:
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


def upgrade() -> None:
    op.create_table(
        'registry_collection_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('project_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('repository_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('artifact_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tag_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'integration_instance_id',
            name='uq_registry_collection_state_integration_instance',
        ),
    )
    op.create_index(
        'ix_registry_collection_states_integration_instance_id',
        'registry_collection_states',
        ['integration_instance_id'],
        unique=False,
    )

    op.create_table(
        'registry_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('repository_count', sa.Integer(), nullable=True),
        sa.Column('provider_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_instance_id', 'name', name='uq_registry_project_instance_name'),
    )
    op.create_index('ix_registry_projects_integration_instance_id', 'registry_projects', ['integration_instance_id'])

    op.create_table(
        'registry_repositories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('artifact_count', sa.Integer(), nullable=True),
        sa.Column('pull_count', sa.BigInteger(), nullable=True),
        sa.Column('provider_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['registry_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_registry_repository_project_name'),
    )
    op.create_index('ix_registry_repositories_project_id', 'registry_repositories', ['project_id'])

    op.create_table(
        'registry_artifacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repository_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('digest', sa.String(length=255), nullable=False),
        sa.Column('artifact_type', sa.String(length=120), nullable=True),
        sa.Column('media_type', sa.String(length=255), nullable=True),
        sa.Column('manifest_media_type', sa.String(length=255), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('push_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pull_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['registry_repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'digest', name='uq_registry_artifact_repository_digest'),
    )
    op.create_index('ix_registry_artifacts_repository_id', 'registry_artifacts', ['repository_id'])

    op.create_table(
        'registry_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.Integer(), nullable=False),
        sa.Column('provider_native_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('push_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pull_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artifact_id'], ['registry_artifacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('artifact_id', 'name', name='uq_registry_tag_artifact_name'),
    )
    op.create_index('ix_registry_tags_artifact_id', 'registry_tags', ['artifact_id'])

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
    view_id = _ensure_permission(bind, permissions, VIEW_PERMISSION, now)
    sync_id = _ensure_permission(bind, permissions, SYNC_PERMISSION, now)
    _grant(bind, permission_id=view_id, role_names=('viewer', 'operator', 'editor', 'admin'), now=now)
    _grant(bind, permission_id=sync_id, role_names=('operator', 'editor', 'admin'), now=now)


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.Integer), sa.column('key', sa.String))
    role_permissions = sa.table('role_permissions', sa.column('permission_id', sa.Integer))
    ids = [
        int(row.id)
        for row in bind.execute(
            sa.select(permissions.c.id).where(
                permissions.c.key.in_([VIEW_PERMISSION[0], SYNC_PERMISSION[0]])
            )
        )
    ]
    if ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(ids)))
        bind.execute(permissions.delete().where(permissions.c.id.in_(ids)))

    op.drop_index('ix_registry_tags_artifact_id', table_name='registry_tags')
    op.drop_table('registry_tags')
    op.drop_index('ix_registry_artifacts_repository_id', table_name='registry_artifacts')
    op.drop_table('registry_artifacts')
    op.drop_index('ix_registry_repositories_project_id', table_name='registry_repositories')
    op.drop_table('registry_repositories')
    op.drop_index('ix_registry_projects_integration_instance_id', table_name='registry_projects')
    op.drop_table('registry_projects')
    op.drop_index(
        'ix_registry_collection_states_integration_instance_id',
        table_name='registry_collection_states',
    )
    op.drop_table('registry_collection_states')
