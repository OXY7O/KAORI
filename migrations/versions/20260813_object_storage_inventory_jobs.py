"""add object storage inventory job permission

Revision ID: 20260813_obj_storage_jobs
Revises: 20260812_obj_storage_inv
Create Date: 2026-08-13
"""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20260813_obj_storage_jobs'
down_revision = '20260812_obj_storage_inv'
branch_labels = None
depends_on = None

PERMISSION = (
    'storage.sync',
    'storage_inventory',
    'sync',
    'Run object-storage inventory synchronization through canonical Job Execution.',
)
ROLE_NAMES = ('operator', 'editor', 'admin')


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
    bind.execute(
        permissions.update()
        .where(permissions.c.key == 'inventory.view')
        .values(
            module='inventory',
            description='View Kubernetes and object-storage inventory pages.',
        )
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
    for role_name in ROLE_NAMES:
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
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Integer),
        sa.column('key', sa.String),
        sa.column('module', sa.String),
        sa.column('description', sa.Text),
    )
    bind.execute(
        permissions.update()
        .where(permissions.c.key == 'inventory.view')
        .values(
            module='k8s_inventory',
            description='View Kubernetes inventory pages.',
        )
    )
    permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == PERMISSION[0])).scalar()
    if permission_id is None:
        return
    role_permissions = sa.table('role_permissions', sa.column('permission_id', sa.Integer))
    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id == permission_id))
    bind.execute(permissions.delete().where(permissions.c.id == permission_id))
