"""retire the non-enforcing Welcome permission

Revision ID: 20260810_retire_welcome_view
Revises: 20260809_auth_session_generation
Create Date: 2026-08-10
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260810_retire_welcome_view'
down_revision = '20260809_auth_session_generation'
branch_labels = None
depends_on = None

RETIRED_PERMISSION_KEY = 'welcome.view'
_DEFAULT_ROLE_NAMES = ('viewer', 'operator', 'editor', 'admin', 'auditor')
_PERMISSION_DESCRIPTION = 'View the KAORI welcome workspace.'


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
    roles = sa.table(
        'roles',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
    )
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    return permissions, roles, role_permissions


def upgrade() -> None:
    """Remove a registry key that never represented a route-level deny boundary."""

    bind = op.get_bind()
    permissions, _roles, role_permissions = _tables()
    permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.key == RETIRED_PERMISSION_KEY))
    if permission_id is None:
        return

    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id == permission_id))
    bind.execute(permissions.delete().where(permissions.c.id == permission_id))


def downgrade() -> None:
    """Restore the historical key and code-owned default-role assignments.

    Custom assignments cannot be reconstructed because the retired permission was
    never an authorization boundary. Downgrade therefore restores only the
    canonical default-role state that existed before this revision.
    """

    bind = op.get_bind()
    permissions, roles, role_permissions = _tables()
    permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.key == RETIRED_PERMISSION_KEY))

    if permission_id is None:
        bind.execute(
            permissions.insert().values(
                key=RETIRED_PERMISSION_KEY,
                module='workspace',
                action='view',
                description=_PERMISSION_DESCRIPTION,
                created_at=datetime.now(UTC),
            )
        )
        permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.key == RETIRED_PERMISSION_KEY))

    if permission_id is None:
        raise RuntimeError('Failed to restore the retired Welcome permission during downgrade.')

    role_rows = bind.execute(sa.select(roles.c.id).where(roles.c.name.in_(_DEFAULT_ROLE_NAMES))).all()
    now = datetime.now(UTC)
    for (role_id,) in role_rows:
        assigned = bind.scalar(
            sa.select(role_permissions.c.role_id).where(
                role_permissions.c.role_id == role_id,
                role_permissions.c.permission_id == permission_id,
            )
        )
        if assigned is None:
            bind.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=permission_id,
                    created_at=now,
                )
            )
