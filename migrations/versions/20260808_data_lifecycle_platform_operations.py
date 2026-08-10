"""move data lifecycle RBAC ownership to platform operations

Revision ID: 20260808_data_lifecycle_ops
Revises: 20260805_notification_deck_v2
Create Date: 2026-08-08 18:00:00
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20260808_data_lifecycle_ops'
down_revision = '20260805_notification_deck_v2'
branch_labels = None
depends_on = None

PERMISSION_RENAMES = (
    (
        'settings.view_data_lifecycle',
        'platform_operations.view_data_lifecycle',
        'view_data_lifecycle',
        'View retention policies, archive storage posture, and lifecycle archive history.',
    ),
    (
        'settings.export_data_lifecycle',
        'platform_operations.export_data_lifecycle',
        'export_data_lifecycle',
        'Download verified data lifecycle archives and manifests.',
    ),
    (
        'settings.manage_data_lifecycle',
        'platform_operations.manage_data_lifecycle',
        'manage_data_lifecycle',
        'Configure policies and run, verify, or maintain lifecycle archives across data domains.',
    ),
)


def _tables():
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
    return permissions, role_permissions


def _rename_permission(*, old_key: str, new_key: str, module: str, action: str, description: str) -> None:
    bind = op.get_bind()
    permissions, role_permissions = _tables()
    now = datetime.now(UTC)

    old_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == old_key)).scalar()
    new_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == new_key)).scalar()

    if old_id is None and new_id is None:
        bind.execute(
            permissions.insert().values(
                key=new_key,
                module=module,
                action=action,
                description=description,
                created_at=now,
            )
        )
        return

    if old_id is not None and new_id is None:
        bind.execute(
            permissions.update()
            .where(permissions.c.id == old_id)
            .values(key=new_key, module=module, action=action, description=description)
        )
        return

    if new_id is not None:
        bind.execute(
            permissions.update()
            .where(permissions.c.id == new_id)
            .values(module=module, action=action, description=description)
        )

    if old_id is None or new_id is None or old_id == new_id:
        return

    role_ids = [
        row.role_id
        for row in bind.execute(sa.select(role_permissions.c.role_id).where(role_permissions.c.permission_id == old_id))
    ]
    for role_id in role_ids:
        exists = bind.execute(
            sa.select(role_permissions.c.role_id).where(
                role_permissions.c.role_id == role_id,
                role_permissions.c.permission_id == new_id,
            )
        ).scalar()
        if exists is None:
            bind.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=new_id,
                    created_at=now,
                )
            )
    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id == old_id))
    bind.execute(permissions.delete().where(permissions.c.id == old_id))


def upgrade() -> None:
    for old_key, new_key, action, description in PERMISSION_RENAMES:
        _rename_permission(
            old_key=old_key,
            new_key=new_key,
            module='operations',
            action=action,
            description=description,
        )


def downgrade() -> None:
    for old_key, new_key, action, description in reversed(PERMISSION_RENAMES):
        _rename_permission(
            old_key=new_key,
            new_key=old_key,
            module='settings',
            action=action,
            description=description,
        )
