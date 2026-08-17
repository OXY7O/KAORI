"""Align Access permission keys with current domain ownership.

Revision ID: 20260817_permission_contract_v1
Revises: 20260817_idp_rbac_split
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260817_permission_contract_v1'
down_revision = '20260817_idp_rbac_split'
branch_labels = None
depends_on = None

RENAMES = (
    {
        'source_key': 'settings.manage_integrations',
        'target_key': 'integrations.manage',
        'module': 'integrations',
        'action': 'manage_integrations',
        'description': 'Manage integration provider registration, bindings, validation, runtime configuration, and delivery channels.',
        'legacy_description': 'Manage Metrics Source, Alertmanager, and reporting integrations.',
    },
    {
        'source_key': 'settings.view_operational_activity',
        'target_key': 'activity_audit.view',
        'module': 'access',
        'action': 'view_operational_activity',
        'description': 'View cross-user operational activity, authentication evidence, and background action audit records.',
        'legacy_description': 'View cross-user operational activity and background action audit records.',
    },
)


def _rename_permission(
    bind,
    permissions,
    *,
    source_key: str,
    target_key: str,
    module: str,
    action: str,
    description: str,
) -> None:
    source_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == source_key)).scalar()
    target_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == target_key)).scalar()
    if source_id is not None and target_id is not None and int(source_id) != int(target_id):
        raise RuntimeError(
            f'Cannot rename RBAC permission {source_key!r} to {target_key!r}: both keys already exist.'
        )
    permission_id = source_id if source_id is not None else target_id
    if permission_id is None:
        return
    bind.execute(
        permissions.update()
        .where(permissions.c.id == permission_id)
        .values(
            key=target_key,
            module=module,
            action=action,
            description=description,
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    permissions = sa.Table('permissions', metadata, autoload_with=bind)
    for contract in RENAMES:
        _rename_permission(
            bind,
            permissions,
            source_key=contract['source_key'],
            target_key=contract['target_key'],
            module=contract['module'],
            action=contract['action'],
            description=contract['description'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    permissions = sa.Table('permissions', metadata, autoload_with=bind)
    for contract in reversed(RENAMES):
        _rename_permission(
            bind,
            permissions,
            source_key=contract['target_key'],
            target_key=contract['source_key'],
            module=contract['module'],
            action=contract['action'],
            description=contract['legacy_description'],
        )
