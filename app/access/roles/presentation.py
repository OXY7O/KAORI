from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.access.roles.forms import DeleteRoleForm, RoleForm
from app.extensions.db import db
from app.models import Role, User
from app.rbac.service import get_permissions_grouped_by_module, get_role_delete_blockers


def build_roles_index_context(*, can_manage_roles: bool) -> dict[str, Any]:
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    permissions_by_module = get_permissions_grouped_by_module()
    role_assignment_counts = {
        int(role_id): int(count)
        for role_id, count in (
            db.session.query(User.role_id, func.count(User.id))
            .filter(User.role_id.is_not(None), User.deleted_at.is_(None))
            .group_by(User.role_id)
            .all()
        )
    }
    role_delete_blockers = {role.id: get_role_delete_blockers(role) for role in roles_list if not role.is_system}
    return {
        'roles': roles_list,
        'permissions_by_module': permissions_by_module,
        'can_manage_roles': can_manage_roles,
        'delete_role_form': DeleteRoleForm(),
        'role_delete_blockers': role_delete_blockers,
        'role_assignment_counts': role_assignment_counts,
        'role_permission_keys': {role.id: role.permission_keys() for role in roles_list},
        'total_permissions': sum(len(items) for items in permissions_by_module.values()),
    }


def build_role_form_context(
    *,
    form: RoleForm,
    role: Role | None,
    clone_source: Role | None,
    view_only: bool,
    selected_permission_ids: set[int],
) -> dict[str, Any]:
    context: dict[str, Any] = {
        'form': form,
        'role': role,
        'clone_source': clone_source,
        'view_only': view_only,
        'permissions_by_module': get_permissions_grouped_by_module(),
        'selected_permission_ids': selected_permission_ids,
    }
    if role is not None:
        context['assigned_user_count'] = User.query.filter(
            User.role_id == role.id,
            User.deleted_at.is_(None),
        ).count()
    return context
