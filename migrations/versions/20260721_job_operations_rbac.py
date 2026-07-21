"""add dedicated jobs and executions permissions

Revision ID: 20260721_job_operations_rbac
Revises: 20260721_data_lifecycle
Create Date: 2026-07-21 10:30:00
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = '20260721_job_operations_rbac'
down_revision = '20260721_data_lifecycle'
branch_labels = None
depends_on = None


PERMISSIONS = (
    (
        'jobs.view',
        'operations',
        'view_jobs',
        'View KAORI background jobs, queue activity, progress, and execution outcomes.',
    ),
    (
        'jobs.cancel',
        'operations',
        'cancel_jobs',
        'Request cancellation for eligible queued, analytics, and forecasting jobs.',
    ),
)


def _assign_permission(bind, role_permissions, role_id: int, permission_id: int, now: datetime) -> None:
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
    for key, module, action, description in PERMISSIONS:
        permission_id = bind.execute(
            sa.select(permissions.c.id).where(permissions.c.key == key)
        ).scalar()
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

    permission_ids = {
        row.key: row.id
        for row in bind.execute(
            sa.select(permissions.c.id, permissions.c.key).where(
                permissions.c.key.in_([item[0] for item in PERMISSIONS])
            )
        )
    }
    roles = sa.table('roles', sa.column('id', sa.Integer), sa.column('name', sa.String))
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )

    default_assignments = {
        'operator': ('jobs.view',),
        'editor': ('jobs.view', 'jobs.cancel'),
        'admin': ('jobs.view', 'jobs.cancel'),
        'auditor': ('jobs.view',),
    }
    for role_name, keys in default_assignments.items():
        role_id = bind.execute(sa.select(roles.c.id).where(roles.c.name == role_name)).scalar()
        if role_id is None:
            continue
        for key in keys:
            permission_id = permission_ids.get(key)
            if permission_id is not None:
                _assign_permission(bind, role_permissions, role_id, permission_id, now)

    # Preserve access for custom roles that previously reached Jobs & Executions
    # through the broader Integrations or operational-governance permissions.
    legacy_mappings = {
        'settings.manage_integrations': ('jobs.view', 'jobs.cancel'),
        'settings.view_data_lifecycle': ('jobs.view',),
        'settings.view_operational_activity': ('jobs.view',),
    }
    legacy_keys = list(legacy_mappings)
    all_keys = legacy_keys + [item[0] for item in PERMISSIONS]
    all_permission_ids = {
        row.key: row.id
        for row in bind.execute(
            sa.select(permissions.c.id, permissions.c.key).where(permissions.c.key.in_(all_keys))
        )
    }
    for legacy_key, target_keys in legacy_mappings.items():
        legacy_id = all_permission_ids.get(legacy_key)
        if legacy_id is None:
            continue
        role_ids = [
            row.role_id
            for row in bind.execute(
                sa.select(role_permissions.c.role_id).where(
                    role_permissions.c.permission_id == legacy_id
                )
            )
        ]
        for role_id in role_ids:
            for target_key in target_keys:
                target_id = all_permission_ids.get(target_key)
                if target_id is not None:
                    _assign_permission(bind, role_permissions, role_id, target_id, now)


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.Integer), sa.column('key', sa.String))
    permission_ids = [
        row.id
        for row in bind.execute(
            sa.select(permissions.c.id).where(
                permissions.c.key.in_([item[0] for item in PERMISSIONS])
            )
        )
    ]
    if permission_ids:
        role_permissions = sa.table('role_permissions', sa.column('permission_id', sa.Integer))
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
        bind.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))
