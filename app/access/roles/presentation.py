from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func

from app.access.rbac.defaults import DEFAULT_PERMISSION_DEPENDENCIES
from app.access.rbac.policy import (
    actor_delegable_permission_keys,
    role_is_delegable_by_actor,
    role_is_mutation_protected,
    role_is_protected_default,
)
from app.access.rbac.service import get_permissions_grouped_by_module
from app.access.roles.baseline import role_baseline_snapshot, role_baseline_state
from app.access.roles.forms import RoleForm
from app.access.roles.service import delegable_permission_ids, role_version_token
from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window, normalize_per_page, positive_int
from app.extensions.db import db
from app.models import IdentityProvider, Permission, Role, User

ROLE_TYPE_OPTIONS = ('all', 'system', 'custom')
ROLE_STATE_OPTIONS = ('all', 'active', 'inactive')


def normalize_role_filters(args: Mapping[str, str | None]) -> dict[str, Any]:
    role_type = (args.get('role_type') or 'all').strip().lower()
    state = (args.get('state') or 'all').strip().lower()
    return {
        'search': (args.get('search') or '').strip(),
        'role_type': role_type if role_type in ROLE_TYPE_OPTIONS else 'all',
        'state': state if state in ROLE_STATE_OPTIONS else 'all',
        'page': positive_int(args.get('page'), 1),
        'per_page': normalize_per_page(args.get('per_page')),
    }


def _required_permission_ids(
    selected_permission_ids: set[int], permissions_by_module: dict[str, list[Permission]]
) -> set[int]:
    permission_by_id = {
        permission.id: permission for permissions in permissions_by_module.values() for permission in permissions
    }
    key_to_id = {permission.key: permission.id for permission in permission_by_id.values()}
    selected_keys = {
        permission_by_id[permission_id].key
        for permission_id in selected_permission_ids
        if permission_id in permission_by_id
    }
    required_keys: set[str] = set()
    pending = list(selected_keys)
    visited: set[str] = set()
    while pending:
        permission_key = pending.pop()
        if permission_key in visited:
            continue
        visited.add(permission_key)
        for dependency_key in DEFAULT_PERMISSION_DEPENDENCIES.get(permission_key, set()):
            required_keys.add(dependency_key)
            pending.append(dependency_key)
    return {key_to_id[key] for key in required_keys if key in key_to_id}


def _role_reference_counts() -> tuple[dict[int, int], dict[int, int]]:
    user_counts = {
        int(role_id): int(count)
        for role_id, count in (
            db.session.query(User.role_id, func.count(User.id))
            .filter(User.role_id.is_not(None), User.deleted_at.is_(None))
            .group_by(User.role_id)
            .all()
        )
    }
    provider_counts = {
        int(role_id): int(count)
        for role_id, count in (
            db.session.query(IdentityProvider.default_role_id, func.count(IdentityProvider.id))
            .filter(IdentityProvider.default_role_id.is_not(None))
            .group_by(IdentityProvider.default_role_id)
            .all()
        )
    }
    return user_counts, provider_counts


def build_roles_index_context(*, can_manage_roles: bool, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized_filters = normalize_role_filters(filters or {})
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    role_assignment_counts, provider_mapping_counts = _role_reference_counts()
    baseline = role_baseline_snapshot(roles_list)
    baseline_states = baseline['states']

    role_rows: list[dict[str, Any]] = []
    for role in roles_list:
        assigned_users = role_assignment_counts.get(role.id, 0)
        provider_mappings = provider_mapping_counts.get(role.id, 0)
        permission_modules = {permission.module for permission in role.permissions}
        protected_default = role_is_protected_default(role)
        mutation_protected = role_is_mutation_protected(role)
        baseline_state = baseline_states[role.id]
        if protected_default:
            type_label, type_short, type_tone, type_icon = 'Default Role', 'Default', 'maintenance', 'shield-check'
        elif role.is_system:
            type_label, type_short, type_tone, type_icon = 'System Drift', 'System Drift', 'warning', 'database-zap'
        else:
            type_label, type_short, type_tone, type_icon = 'Custom Role', 'Custom', 'info', 'user-cog'
        role_rows.append(
            {
                'record': role,
                'type': {
                    'label': type_label,
                    'short_label': type_short,
                    'tone': type_tone,
                    'icon': type_icon,
                },
                'state': {
                    'label': 'Active' if role.is_active else 'Inactive',
                    'tone': 'normal' if role.is_active else 'unknown',
                    'icon': 'circle-check' if role.is_active else 'pause-circle',
                },
                'baseline': baseline_state,
                'protected_default': protected_default,
                'mutation_protected': mutation_protected,
                'assigned_users': assigned_users,
                'provider_mappings': provider_mappings,
                'permission_count': len(role.permissions),
                'module_count': len(permission_modules),
                'delete_blocked': bool(assigned_users or provider_mappings or mutation_protected),
                'delete_eligible': bool(not mutation_protected and not assigned_users and not provider_mappings),
                'version_token': role_version_token(role),
                'search_text': ' '.join(filter(None, (role.display_name, role.name, role.description or ''))).lower(),
            }
        )

    search = normalized_filters['search'].lower()
    filtered_rows = role_rows
    if search:
        filtered_rows = [row for row in filtered_rows if search in row['search_text']]
    if normalized_filters['role_type'] == 'system':
        filtered_rows = [row for row in filtered_rows if row['mutation_protected']]
    elif normalized_filters['role_type'] == 'custom':
        filtered_rows = [row for row in filtered_rows if not row['mutation_protected']]
    if normalized_filters['state'] == 'active':
        filtered_rows = [row for row in filtered_rows if row['record'].is_active]
    elif normalized_filters['state'] == 'inactive':
        filtered_rows = [row for row in filtered_rows if not row['record'].is_active]

    pagination = build_pagination_window(
        total_items=len(filtered_rows),
        page=normalized_filters['page'],
        per_page=normalized_filters['per_page'],
    )
    page_rows = filtered_rows[pagination.offset : pagination.offset + pagination.per_page]

    protected_defaults = sum(1 for row in role_rows if row['protected_default'])
    custom_roles = sum(1 for row in role_rows if not row['mutation_protected'])
    active_roles = sum(1 for row in role_rows if row['record'].is_active)
    assigned_users = sum(row['assigned_users'] for row in role_rows)
    inactive_assigned_users = sum(row['assigned_users'] for row in role_rows if not row['record'].is_active)
    total_permissions = Permission.query.count()
    baseline_drift_count = int(baseline['drift_count'])

    if active_roles == 0 or inactive_assigned_users or baseline_drift_count:
        posture_label, posture_tone = 'Review Required', 'warning'
    else:
        posture_label, posture_tone = 'Ready', 'normal'

    return {
        'role_rows': page_rows,
        'can_manage_roles': can_manage_roles,
        'summary': {
            'total_roles': len(role_rows),
            'system_roles': protected_defaults,
            'custom_roles': custom_roles,
            'active_roles': active_roles,
            'assigned_users': assigned_users,
            'inactive_assigned_users': inactive_assigned_users,
            'total_permissions': total_permissions,
            'baseline_drift_count': baseline_drift_count,
            'missing_default_roles': len(baseline['missing_defaults']),
            'unexpected_system_roles': int(baseline['unexpected_system_count']),
            'matching': len(filtered_rows),
            'posture_label': posture_label,
            'posture_tone': posture_tone,
        },
        'filters': {
            **normalized_filters,
            'page': pagination.page,
            'per_page': pagination.per_page,
        },
        'pagination': pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'pagination_query': {
            'per_page': pagination.per_page,
            'search': normalized_filters['search'],
            'role_type': normalized_filters['role_type'],
            'state': normalized_filters['state'],
        },
    }


def build_role_form_context(
    *,
    form: RoleForm,
    actor: User,
    role: Role | None,
    clone_source: Role | None,
    view_only: bool,
    selected_permission_ids: set[int],
) -> dict[str, Any]:
    permissions_by_module = get_permissions_grouped_by_module()
    permitted_ids = delegable_permission_ids(actor)
    delegable_ids = (
        {permission.id for permissions in permissions_by_module.values() for permission in permissions}
        if permitted_ids is None
        else permitted_ids
    )
    delegable_keys = actor_delegable_permission_keys(actor)
    context: dict[str, Any] = {
        'form': form,
        'role': role,
        'clone_source': clone_source,
        'view_only': view_only,
        'permissions_by_module': permissions_by_module,
        'selected_permission_ids': selected_permission_ids,
        'required_permission_ids': _required_permission_ids(selected_permission_ids, permissions_by_module),
        'delegable_permission_ids': delegable_ids,
        'delegation_limited': delegable_keys is not None,
        'assigned_user_count': 0,
        'identity_provider_count': 0,
        'protected_default': bool(role and role_is_mutation_protected(role)),
        'baseline_state': role_baseline_state(role) if role is not None else None,
        'can_mutate_role': bool(
            role
            and actor.has_permission('roles.manage')
            and not role_is_mutation_protected(role)
            and role_is_delegable_by_actor(actor, role)
        ),
        'can_clone_source': bool(
            clone_source
            and actor.has_permission('roles.manage')
            and role_is_protected_default(clone_source)
            and role_is_delegable_by_actor(actor, clone_source)
        ),
    }
    if role is not None:
        context['assigned_user_count'] = User.query.filter(
            User.role_id == role.id,
            User.deleted_at.is_(None),
        ).count()
        context['identity_provider_count'] = IdentityProvider.query.filter(
            IdentityProvider.default_role_id == role.id
        ).count()
    return context


def build_role_detail_context(*, role: Role, actor: User) -> dict[str, Any]:
    assigned_users = User.query.filter(User.role_id == role.id, User.deleted_at.is_(None)).count()
    provider_mappings = IdentityProvider.query.filter(IdentityProvider.default_role_id == role.id).count()
    baseline_state = role_baseline_state(role)
    mutation_protected = role_is_mutation_protected(role)
    can_manage_roles = actor.has_permission('roles.manage')
    within_delegation = role_is_delegable_by_actor(actor, role)

    permissions = sorted(role.permissions, key=lambda item: (item.module or '', item.key))
    module_map: dict[str, list[Permission]] = {}
    for permission in permissions:
        module_map.setdefault(permission.module or 'general', []).append(permission)

    permission_modules = [
        {
            'key': module_name,
            'label': module_name.replace('_', ' ').title(),
            'count': len(module_permissions),
            'permissions': [
                {
                    'key': permission.key,
                    'label': (permission.action or permission.key.rsplit('.', 1)[-1]).replace('_', ' ').title(),
                    'description': permission.description or 'No permission description is defined.',
                }
                for permission in module_permissions
            ],
        }
        for module_name, module_permissions in sorted(module_map.items())
    ]

    delete_blocked = bool(assigned_users or provider_mappings or mutation_protected)
    return {
        'role': role,
        'can_manage_roles': can_manage_roles,
        'can_mutate_role': bool(can_manage_roles and not mutation_protected and within_delegation),
        'detail': {
            'type_label': 'Default Role'
            if role_is_protected_default(role)
            else ('System Drift' if role.is_system else 'Custom Role'),
            'type_short': 'Default'
            if role_is_protected_default(role)
            else ('System Drift' if role.is_system else 'Custom'),
            'type_icon': 'shield-check' if mutation_protected else 'user-cog',
            'state_label': 'Active' if role.is_active else 'Inactive',
            'state_tone': 'normal' if role.is_active else 'unknown',
            'state_icon': 'circle-check' if role.is_active else 'pause-circle',
            'baseline_label': baseline_state.label,
            'baseline_tone': baseline_state.tone,
            'baseline_icon': baseline_state.icon,
            'baseline_detail': baseline_state.detail,
            'assigned_users': assigned_users,
            'provider_mappings': provider_mappings,
            'permission_count': len(permissions),
            'module_count': len(permission_modules),
            'permission_modules': permission_modules,
            'delete_blocked': delete_blocked,
            'delete_eligible': bool(not mutation_protected and not delete_blocked and within_delegation),
            'version_token': role_version_token(role),
            'within_delegation': within_delegation,
            'mutation_protected': mutation_protected,
            'assignment_effect': (
                'Assigned users receive no permissions from this inactive role.'
                if not role.is_active and assigned_users
                else 'Role assignments are evaluated on each protected authorization check.'
            ),
        },
    }
