from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

from app.extensions.db import db
from app.models import IdentityProvider, Permission, Role, RolePermission, User
from app.rbac.defaults import DEFAULT_PERMISSIONS, DEFAULT_ROLE_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS

ROLE_SLUG_PATTERN = re.compile(r'[^a-z0-9_]+')

# Action permissions that require a baseline view permission. The service expands
# selected permissions so custom roles cannot be saved in an internally
# inconsistent state such as users.manage without users.view.
PERMISSION_DEPENDENCIES: dict[str, set[str]] = {
    'clusters.manage': {'clusters.view'},
    'clusters.sync': {'clusters.view', 'jobs.execute'},
    'storage.sync': {'inventory.view', 'jobs.execute'},
    'kubernetes_configmaps.create': {'kubernetes_configmaps.view'},
    'kubernetes_configmaps.update': {'kubernetes_configmaps.view'},
    'kubernetes_configmaps.delete': {'kubernetes_configmaps.view'},
    'kubernetes_secrets.create': {'kubernetes_secrets.view'},
    'kubernetes_secrets.replace': {'kubernetes_secrets.view'},
    'kubernetes_secrets.delete': {'kubernetes_secrets.view'},
    'kubernetes_secrets.reveal': {'kubernetes_secrets.view'},
    'kubernetes_secrets.approve_reveal': {'kubernetes_secrets.view'},
    'kubernetes_secrets.manage_reveal': {'kubernetes_secrets.view'},
    'kubernetes_secrets.rotate_tls': {'kubernetes_secrets.view'},
    'kubernetes_secrets.bulk_rotate_tls': {'kubernetes_secrets.view'},
    'tls_certificates.sync': {'tls_certificates.view'},
    'reports.generate': {'reports.view'},
    'reports.manage_templates': {'reports.view'},
    'reports.manage_schedules': {'reports.view'},
    'reports.manage_storage': {'reports.view'},
    'jobs.cancel': {'jobs.view'},
    'jobs.execute': {'jobs.view'},
    'jobs.configure': {'jobs.view'},
    'knowledge.runbooks.manage': {'knowledge.runbooks.view'},
    'knowledge.runbooks.publish': {'knowledge.runbooks.view', 'knowledge.runbooks.manage'},
    'intelligence.decisions.create': {'intelligence.decisions.view'},
    'intelligence.decisions.approve': {'intelligence.decisions.view'},
    'intelligence.decisions.execute': {'intelligence.decisions.view'},
    'platform_operations.export_data_lifecycle': {'platform_operations.view_data_lifecycle'},
    'platform_operations.manage_data_lifecycle': {'platform_operations.view_data_lifecycle'},
    'users.manage': {'users.view'},
    'users.reset_password': {'users.view'},
    'users.activate': {'users.view'},
    'users.delete': {'users.view'},
    'roles.manage': {'roles.view'},
    'system.manage': {'system.view'},
}


def normalize_role_slug(value: str | None) -> str:
    normalized = (value or '').strip().lower().replace('-', '_').replace(' ', '_')
    normalized = ROLE_SLUG_PATTERN.sub('_', normalized)
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    return normalized


def role_slug_exists(slug: str, *, exclude_role_id: int | None = None) -> bool:
    query = Role.query.filter(Role.name == slug)
    if exclude_role_id is not None:
        query = query.filter(Role.id != exclude_role_id)
    return db.session.query(query.exists()).scalar()


def seed_default_rbac() -> dict[str, int]:
    permission_by_key: dict[str, Permission] = {}

    for key, module, action, description in DEFAULT_PERMISSIONS:
        permission = Permission.query.filter_by(key=key).first()
        if permission is None:
            permission = Permission()
            permission.key = key
            db.session.add(permission)
        permission.module = module
        permission.action = action
        permission.description = description
        permission_by_key[key] = permission

    db.session.flush()

    role_by_name: dict[str, Role] = {}
    for name, definition in DEFAULT_ROLE_DEFINITIONS.items():
        role = Role.query.filter_by(name=name).first()
        if role is None:
            role = Role()
            role.name = name
            db.session.add(role)
        role.display_name = definition['display_name']
        role.description = definition['description']
        role.is_system = True
        role.is_active = True
        role_by_name[name] = role

    db.session.flush()

    for role_name, permission_keys in DEFAULT_ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        existing_by_key = {
            role_permission.permission.key: role_permission
            for role_permission in role.role_permissions
            if role_permission.permission
        }

        # System roles are code-owned baselines. Seeding is convergent: it adds
        # missing assignments and removes assignments that are not part of the
        # current canonical definition.
        for permission_key, role_permission in existing_by_key.items():
            if permission_key not in permission_keys:
                db.session.delete(role_permission)

        for permission_key in permission_keys - set(existing_by_key):
            permission = permission_by_key.get(permission_key)
            if permission is None:
                continue
            role_permission = RolePermission()
            role_permission.role_id = role.id
            role_permission.permission_id = permission.id
            db.session.add(role_permission)
    db.session.commit()

    return {
        'permissions': len(permission_by_key),
        'roles': len(role_by_name),
    }


def get_active_roles() -> list[Role]:
    return Role.query.filter_by(is_active=True).order_by(Role.is_system.desc(), Role.display_name.asc()).all()


def get_permissions_grouped_by_module() -> dict[str, list[Permission]]:
    grouped: dict[str, list[Permission]] = defaultdict(list)
    permissions = Permission.query.order_by(Permission.module.asc(), Permission.key.asc()).all()
    for permission in permissions:
        grouped[permission.module].append(permission)
    return dict(grouped)


def expand_permission_keys(permission_keys: Iterable[str]) -> set[str]:
    expanded = {str(key) for key in permission_keys}
    pending = list(expanded)
    while pending:
        permission_key = pending.pop()
        for dependency_key in PERMISSION_DEPENDENCIES.get(permission_key, set()):
            if dependency_key not in expanded:
                expanded.add(dependency_key)
                pending.append(dependency_key)
    return expanded


def expand_permission_ids(permission_ids: Iterable[int]) -> set[int]:
    selected_ids = {int(permission_id) for permission_id in permission_ids}
    if not selected_ids:
        return set[int]()

    selected_permissions = Permission.query.filter(Permission.id.in_(selected_ids)).all()
    selected_keys = {permission.key for permission in selected_permissions}
    expanded_keys = expand_permission_keys(selected_keys)
    expanded_permissions = Permission.query.filter(Permission.key.in_(expanded_keys)).all()
    return {permission.id for permission in expanded_permissions}


def replace_role_permissions(role: Role, permission_ids: Iterable[int]) -> set[int]:
    if role.is_system:
        raise ValueError('System role permissions are code-owned and cannot be replaced.')

    selected_ids = expand_permission_ids(permission_ids)
    existing_by_permission_id = {
        role_permission.permission_id: role_permission for role_permission in role.role_permissions
    }

    for permission_id, role_permission in existing_by_permission_id.items():
        if permission_id not in selected_ids:
            db.session.delete(role_permission)

    for permission_id in sorted(selected_ids - set(existing_by_permission_id)):
        role_permission = RolePermission()
        role_permission.role_id = role.id
        role_permission.permission_id = permission_id
        db.session.add(role_permission)

    return selected_ids


def get_role_delete_blockers(role: Role) -> dict[str, int]:
    return {
        'assigned_users': User.query.filter(User.role_id == role.id, User.deleted_at.is_(None)).count(),
        'identity_providers': IdentityProvider.query.filter(IdentityProvider.default_role_id == role.id).count(),
    }
