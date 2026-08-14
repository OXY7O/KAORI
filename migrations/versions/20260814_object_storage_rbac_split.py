"""split Object Storage inventory and analytics RBAC

Revision ID: 20260814_obj_storage_rbac
Revises: 20260814_report_notify_channels
Create Date: 2026-08-14
"""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20260814_obj_storage_rbac'
down_revision = '20260814_report_notify_channels'
branch_labels = None
depends_on = None

PERMISSIONS = (
    (
        'object_storage_inventory.view',
        'storage_inventory',
        'view',
        'View committed Object Storage systems, buckets, containers, and inventory evidence.',
        'inventory.view',
    ),
    (
        'object_storage_analytics.view',
        'storage_analytics',
        'view',
        'View Object Storage capacity, performance, forecast, consumer, and alert analytics.',
        'analytics.view',
    ),
)


def _ensure_permission(
    bind,
    permissions,
    *,
    key: str,
    module: str,
    action: str,
    description: str,
    now: datetime,
) -> int:
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
    else:
        bind.execute(
            permissions.update()
            .where(permissions.c.id == permission_id)
            .values(module=module, action=action, description=description)
        )
    return int(permission_id)


def _copy_role_assignments(bind, role_permissions, *, source_id: int, target_id: int, now: datetime) -> None:
    role_ids = [
        int(row.role_id)
        for row in bind.execute(
            sa.select(role_permissions.c.role_id).where(role_permissions.c.permission_id == source_id)
        )
    ]
    for role_id in role_ids:
        exists = bind.execute(
            sa.select(role_permissions.c.role_id).where(
                role_permissions.c.role_id == role_id,
                role_permissions.c.permission_id == target_id,
            )
        ).scalar()
        if exists is None:
            bind.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=target_id,
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
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )

    # Restore the legacy inventory permission to its Kubernetes-only ownership.
    bind.execute(
        permissions.update()
        .where(permissions.c.key == 'inventory.view')
        .values(
            module='k8s_inventory',
            action='view',
            description='View Kubernetes inventory pages.',
        )
    )

    for key, module, action, description, legacy_key in PERMISSIONS:
        target_id = _ensure_permission(
            bind,
            permissions,
            key=key,
            module=module,
            action=action,
            description=description,
            now=now,
        )
        legacy_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == legacy_key)).scalar()
        if legacy_id is not None:
            # Preserve existing system and custom-role access at migration time.
            _copy_role_assignments(
                bind,
                role_permissions,
                source_id=int(legacy_id),
                target_id=target_id,
                now=now,
            )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Integer),
        sa.column('key', sa.String),
        sa.column('module', sa.String),
        sa.column('action', sa.String),
        sa.column('description', sa.Text),
    )
    role_permissions = sa.table(
        'role_permissions',
        sa.column('permission_id', sa.Integer),
    )

    permission_ids = [
        int(row.id)
        for row in bind.execute(
            sa.select(permissions.c.id).where(permissions.c.key.in_([item[0] for item in PERMISSIONS]))
        )
    ]
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
        bind.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))

    bind.execute(
        permissions.update()
        .where(permissions.c.key == 'inventory.view')
        .values(
            module='inventory',
            action='view',
            description='View Kubernetes and object-storage inventory pages.',
        )
    )
