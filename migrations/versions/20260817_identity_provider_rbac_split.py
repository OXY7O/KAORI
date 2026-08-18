"""Split Identity Provider administration from User Management RBAC.

Revision ID: 20260817_idp_rbac_split
Revises: 20260817_identity_provider_v1
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260817_idp_rbac_split'
down_revision = '20260817_identity_provider_v1'
branch_labels = None
depends_on = None

PERMISSIONS = (
    (
        'identity_providers.view',
        'access',
        'view_identity_providers',
        'View configured authentication providers, posture, and identity-link evidence.',
    ),
    (
        'identity_providers.manage',
        'access',
        'manage_identity_providers',
        'Configure, validate, enable, and update authentication providers.',
    ),
    (
        'identity_providers.provision',
        'access',
        'provision_external_identities',
        'Search directory providers and project external identities into KAORI user accounts.',
    ),
)


def _ensure_permission(
    bind, permissions, *, key: str, module: str, action: str, description: str, now: datetime
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

    legacy_permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == 'users.manage')).scalar()
    if legacy_permission_id is None:
        raise RuntimeError('users.manage must exist before Identity Provider RBAC can be split safely.')

    for key, module, action, description in PERMISSIONS:
        permission_id = _ensure_permission(
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
            role_permissions,
            source_id=int(legacy_permission_id),
            target_id=permission_id,
            now=now,
        )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Integer),
        sa.column('key', sa.String),
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
