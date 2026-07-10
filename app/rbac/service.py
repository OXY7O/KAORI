from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.extensions import db
from app.models import Permission, Role, RolePermission, User
from app.rbac.defaults import DEFAULT_PERMISSIONS, DEFAULT_ROLE_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS


def seed_default_rbac() -> dict[str, int]:
    permission_by_key: dict[str, Permission] = {}

    for key, module, action, description in DEFAULT_PERMISSIONS:
        permission = Permission.query.filter_by(key=key).first()
        if permission is None:
            permission = Permission()
            permission.key = key
            permission.module = module
            permission.action = action
            permission.description = description
            db.session.add(permission)
        else:
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
        existing_keys = {
            role_permission.permission.key for role_permission in role.role_permissions if role_permission.permission
        }
        for permission_key in permission_keys - existing_keys:
            permission = permission_by_key.get(permission_key)
            if permission is None:
                continue
            role_permission = RolePermission()
            role_permission.role_id = role.id
            role_permission.permission_id = permission.id
            db.session.add(role_permission)

    # Backfill role_id from the legacy User.role string.
    for user in User.query.all():
        if user.role_id is None:
            role = role_by_name.get(user.role or 'viewer') or role_by_name.get('viewer')
            if role is not None:
                user.role_id = role.id

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


def replace_role_permissions(role: Role, permission_ids: Iterable[int]) -> None:
    selected_ids = {int(permission_id) for permission_id in permission_ids}
    role.role_permissions.clear()
    db.session.flush()
    for permission_id in selected_ids:
        role_permission = RolePermission()
        role_permission.role_id = role.id
        role_permission.permission_id = permission_id
        db.session.add(role_permission)
