"""Harden Activity Audit actor, category, and recipient evidence boundaries.

Revision ID: 20260817_activity_audit_v1
Revises: 20260817_permission_contract_v1
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = '20260817_activity_audit_v1'
down_revision = '20260817_permission_contract_v1'
branch_labels = None
depends_on = None


def _category_key(event_type: object) -> str:
    event = str(event_type or '').strip().lower()
    if event.startswith('kubernetes_configmap_'):
        return 'configmap_management'
    if event.startswith(('governance_tls_', 'kubernetes_tls_secret_')):
        return 'tls_certificate'
    if event.startswith(
        (
            'kubernetes_secret_reveal_cluster_readiness_',
            'kubernetes_secret_reveal_namespace_policy_',
            'data_lifecycle_',
            'job_',
            'report_',
            'generated_report_',
            'generated_reports_',
        )
    ):
        return 'platform_operations'
    if event.startswith('kubernetes_secret_'):
        return 'secret_management'
    if event == 'kubernetes_inventory_sync' or event.startswith(
        (
            'metrics_source_',
            'alertmanager_',
            'cluster_',
            'kubernetes_capability_',
            'kubernetes_runtime_',
            'integration_',
        )
    ):
        return 'integrations'
    if event in {'user_preference', 'account_security'} or event.startswith('settings_'):
        return 'settings'
    if event == 'authentication' or event.startswith(('rbac_', 'identity_provider_', 'external_identity_', 'user_')):
        return 'access'
    return 'operations'


def _system_actor() -> dict[str, Any]:
    return {
        'schema': 'activity_actor.v1',
        'key': 'system:kaori',
        'type': 'system',
        'user_id': None,
        'label': 'KAORI System',
        'email': None,
        'role': 'System Runtime',
        'auth_source': 'internal',
    }


def _unauthenticated_actor() -> dict[str, Any]:
    return {
        'schema': 'activity_actor.v1',
        'key': 'unauthenticated',
        'type': 'unauthenticated',
        'user_id': None,
        'label': 'Unauthenticated Request',
        'email': None,
        'role': 'No Authenticated Role',
        'auth_source': 'unauthenticated',
    }


def _user_actor(user: dict[str, Any]) -> dict[str, Any]:
    label = str(user.get('display_name') or '').strip() or str(user.get('username') or f"User #{user['id']}")
    role = 'Local Database Super Admin' if bool(user.get('is_super_admin')) else str(user.get('role_label') or 'Unassigned')
    return {
        'schema': 'activity_actor.v1',
        'key': f"user:{user['id']}",
        'type': 'user',
        'user_id': int(user['id']),
        'label': label,
        'email': user.get('email'),
        'role': role,
        'auth_source': str(user.get('auth_source') or 'database'),
    }


def _actor_snapshot(row: dict[str, Any], users: dict[int, dict[str, Any]]) -> dict[str, Any]:
    metadata = row.get('metadata_json') if isinstance(row.get('metadata_json'), dict) else {}
    if row.get('event_type') == 'authentication' and str(metadata.get('result') or '').lower() == 'failed':
        return _unauthenticated_actor()

    actor_user_id = metadata.get('actor_user_id')
    try:
        actor_user_id = int(actor_user_id) if actor_user_id is not None else None
    except (TypeError, ValueError):
        actor_user_id = None

    actor_display_name = str(metadata.get('actor_display_name') or '').strip()
    if actor_display_name:
        effective_user_id = actor_user_id or row.get('user_id')
        try:
            effective_user_id = int(effective_user_id) if effective_user_id is not None else None
        except (TypeError, ValueError):
            effective_user_id = None
        return {
            'schema': 'activity_actor.v1',
            'key': f'user:{effective_user_id}' if effective_user_id else 'user:historical',
            'type': 'user',
            'user_id': effective_user_id,
            'label': actor_display_name,
            'email': metadata.get('actor_email'),
            'role': str(metadata.get('actor_role') or 'Unassigned'),
            'auth_source': str(metadata.get('auth_source') or 'database'),
        }

    for candidate in (actor_user_id, row.get('user_id')):
        try:
            user_id = int(candidate) if candidate is not None else None
        except (TypeError, ValueError):
            user_id = None
        if user_id is not None and user_id in users:
            return _user_actor(users[user_id])

    return _system_actor()


def upgrade() -> None:
    op.add_column('notifications', sa.Column('category_key', sa.String(length=80), nullable=True))
    op.add_column('notifications', sa.Column('actor_key', sa.String(length=160), nullable=True))
    op.add_column('notifications', sa.Column('actor_label', sa.String(length=255), nullable=True))
    op.add_column('notifications', sa.Column('actor_snapshot_json', sa.JSON(), nullable=True))

    bind = op.get_bind()
    metadata = sa.MetaData()
    notifications = sa.Table('notifications', metadata, autoload_with=bind)
    users_table = sa.Table('users', metadata, autoload_with=bind)
    roles_table = sa.Table('roles', metadata, autoload_with=bind)

    users: dict[int, dict[str, Any]] = {}
    user_rows = bind.execute(
        sa.select(
            users_table.c.id,
            users_table.c.username,
            users_table.c.display_name,
            users_table.c.email,
            users_table.c.auth_source,
            users_table.c.is_super_admin,
            roles_table.c.display_name.label('role_label'),
        ).select_from(users_table.outerjoin(roles_table, users_table.c.role_id == roles_table.c.id))
    )
    for row in user_rows.mappings():
        users[int(row['id'])] = dict(row)

    for row in bind.execute(
        sa.select(
            notifications.c.id,
            notifications.c.user_id,
            notifications.c.event_type,
            notifications.c.metadata_json,
        )
    ).mappings():
        row_dict = dict(row)
        actor = _actor_snapshot(row_dict, users)
        bind.execute(
            notifications.update()
            .where(notifications.c.id == row['id'])
            .values(
                category_key=_category_key(row['event_type']),
                actor_key=actor['key'],
                actor_label=actor['label'],
                actor_snapshot_json=actor,
            )
        )

    op.alter_column('notifications', 'category_key', existing_type=sa.String(length=80), nullable=False)
    op.alter_column('notifications', 'actor_key', existing_type=sa.String(length=160), nullable=False)
    op.alter_column('notifications', 'actor_label', existing_type=sa.String(length=255), nullable=False)
    op.alter_column('notifications', 'actor_snapshot_json', existing_type=sa.JSON(), nullable=False)

    op.create_index('ix_notifications_category_created', 'notifications', ['category_key', 'created_at'], unique=False)
    op.create_index('ix_notifications_actor_created', 'notifications', ['actor_key', 'created_at'], unique=False)

    op.drop_constraint('notifications_user_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key(
        'notifications_user_id_fkey',
        'notifications',
        'users',
        ['user_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('notifications_user_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key(
        'notifications_user_id_fkey',
        'notifications',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.drop_index('ix_notifications_actor_created', table_name='notifications')
    op.drop_index('ix_notifications_category_created', table_name='notifications')
    op.drop_column('notifications', 'actor_snapshot_json')
    op.drop_column('notifications', 'actor_label')
    op.drop_column('notifications', 'actor_key')
    op.drop_column('notifications', 'category_key')
