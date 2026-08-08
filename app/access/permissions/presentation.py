from __future__ import annotations

from typing import Any

from app.models import Permission, Role
from app.rbac.service import get_permissions_grouped_by_module, seed_default_rbac


def build_permission_catalog_context() -> dict[str, Any]:
    seed_default_rbac()
    permissions_by_module = get_permissions_grouped_by_module()
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    permissions = Permission.query.order_by(
        Permission.module.asc(),
        Permission.action.asc(),
        Permission.key.asc(),
    ).all()
    return {
        'permissions': permissions,
        'permissions_by_module': permissions_by_module,
        'roles': roles_list,
        'total_permissions': len(permissions),
        'total_modules': len(permissions_by_module),
        'assignment_count': sum(len(permission.role_permissions) for permission in permissions),
    }
