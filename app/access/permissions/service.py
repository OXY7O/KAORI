from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models import IdentityProvider, Permission, Role
from app.rbac.defaults import (
    ACCESS_ADMINISTRATION_PERMISSIONS,
    DEFAULT_PERMISSION_DEPENDENCIES,
    DEFAULT_PERMISSIONS,
    PERMISSION_MODULE_LABELS,
)

REGISTRY_STATE_PRESENTATION: dict[str, dict[str, str]] = {
    'canonical': {'label': 'Canonical', 'tone': 'normal', 'icon': 'circle-check'},
    'missing': {'label': 'Missing From Registry', 'tone': 'warning', 'icon': 'database-zap'},
    'metadata_drift': {'label': 'Metadata Drift', 'tone': 'warning', 'icon': 'triangle-alert'},
    'database_only': {'label': 'Database Only', 'tone': 'warning', 'icon': 'database'},
}

DELEGATION_TIER_PRESENTATION: dict[str, dict[str, str]] = {
    'standard': {'label': 'Standard Capability', 'tone': 'normal', 'icon': 'key-round'},
    'access_admin': {'label': 'Access Administration', 'tone': 'warning', 'icon': 'shield-alert'},
}


def module_label(value: str | None) -> str:
    key = (value or 'general').strip().lower()
    return PERMISSION_MODULE_LABELS.get(key, key.replace('_', ' ').title())


def action_label(value: str | None) -> str:
    return (value or 'view').replace('_', ' ').title()


def permission_title(key: str, action: str | None) -> str:
    return action_label(action or key.rsplit('.', 1)[-1])


def _delegation_tier(permission_key: str) -> tuple[str, dict[str, str]]:
    key = 'access_admin' if permission_key in ACCESS_ADMINISTRATION_PERMISSIONS else 'standard'
    return key, DELEGATION_TIER_PRESENTATION[key]


def _inverse_dependencies() -> dict[str, set[str]]:
    inverse: dict[str, set[str]] = defaultdict(set)
    for permission_key, dependencies in DEFAULT_PERMISSION_DEPENDENCIES.items():
        for dependency_key in dependencies:
            inverse[dependency_key].add(permission_key)
    return dict(inverse)


def _dependency_closure(permission_key: str) -> set[str]:
    resolved: set[str] = set()
    pending = list(DEFAULT_PERMISSION_DEPENDENCIES.get(permission_key, set()))
    while pending:
        dependency_key = pending.pop()
        if dependency_key in resolved:
            continue
        resolved.add(dependency_key)
        pending.extend(DEFAULT_PERMISSION_DEPENDENCIES.get(dependency_key, set()))
    return resolved


def _registry_state(canonical: dict[str, str], database_permission: Permission | None) -> str:
    if database_permission is None:
        return 'missing'
    if (
        database_permission.module != canonical['module']
        or database_permission.action != canonical['action']
        or (database_permission.description or '') != (canonical['description'] or '')
    ):
        return 'metadata_drift'
    return 'canonical'


def _role_impact(
    roles: list[Role],
    *,
    enabled_jit_providers_by_role: dict[int, list[IdentityProvider]],
) -> dict[str, int]:
    active_user_ids = {int(user.id) for role in roles for user in role.users if user.id is not None and user.is_active}
    jit_provider_ids = {
        int(provider.id)
        for role in roles
        for provider in enabled_jit_providers_by_role.get(int(role.id), [])
        if provider.id is not None
    }
    return {
        'active_user_count': len(active_user_ids),
        'jit_provider_count': len(jit_provider_ids),
    }


def _build_contract_row(
    *,
    key: str,
    canonical: dict[str, str] | None,
    database_permission: Permission | None,
    roles: list[Role],
    inverse_dependencies: dict[str, set[str]],
    enabled_jit_providers_by_role: dict[int, list[IdentityProvider]],
) -> dict[str, Any]:
    code_owned = canonical is not None
    module = canonical['module'] if canonical else str(database_permission.module)
    action = canonical['action'] if canonical else str(database_permission.action)
    description = canonical['description'] if canonical else database_permission.description
    state_key = _registry_state(canonical, database_permission) if canonical else 'database_only'
    delegation_tier_key, delegation_tier = _delegation_tier(key)
    role_impact = _role_impact(roles, enabled_jit_providers_by_role=enabled_jit_providers_by_role)
    requires = sorted(DEFAULT_PERMISSION_DEPENDENCIES.get(key, set()))
    effective_requires = sorted(_dependency_closure(key))

    return {
        'key': key,
        'module': module,
        'action': action,
        'description': description,
        'title': permission_title(key, action),
        'module_label': module_label(module),
        'database_id': database_permission.id if database_permission else None,
        'database_module': database_permission.module if database_permission else None,
        'database_action': database_permission.action if database_permission else None,
        'database_description': database_permission.description if database_permission else None,
        'created_at': database_permission.created_at if database_permission else None,
        'state_key': state_key,
        'state': REGISTRY_STATE_PRESENTATION[state_key],
        'code_owned': code_owned,
        'delegation_tier_key': delegation_tier_key,
        'delegation_tier': delegation_tier,
        'is_access_administration': delegation_tier_key == 'access_admin',
        'requires': requires,
        'effective_requires': effective_requires,
        'required_by': sorted(inverse_dependencies.get(key, set())),
        'roles': roles,
        'role_count': len(roles),
        **role_impact,
    }


def _roles_by_permission_key(roles: list[Role]) -> dict[str, list[Role]]:
    mapping: dict[str, list[Role]] = defaultdict(list)
    for role in roles:
        for permission in role.permissions:
            mapping[permission.key].append(role)
    return dict(mapping)


def _enabled_jit_providers_by_role() -> dict[int, list[IdentityProvider]]:
    mapping: dict[int, list[IdentityProvider]] = defaultdict(list)
    providers = IdentityProvider.query.filter(
        IdentityProvider.enabled.is_(True),
        IdentityProvider.jit_enabled.is_(True),
        IdentityProvider.default_role_id.is_not(None),
    ).all()
    for provider in providers:
        if provider.default_role_id is not None:
            mapping[int(provider.default_role_id)].append(provider)
    return dict(mapping)


def _registry_summary(
    *,
    contracts: list[dict[str, Any]],
    database_permissions: list[Permission],
    roles: list[Role],
    modules: list[str],
) -> dict[str, Any]:
    modules = sorted({row['module'] for row in contracts}, key=module_label)
    summary = _registry_summary(
        contracts=contracts,
        database_permissions=database_permissions,
        roles=roles,
        modules=modules,
    )

    return {
        'canonical_permissions': len(canonical_contracts),
        'registered_permissions': len(database_permissions),
        'control_modules': len(modules),
        'role_mappings': sum(len(role.permissions) for role in roles),
        'unused_contracts': sum(1 for row in canonical_contracts if row['role_count'] == 0),
        'access_administration_contracts': sum(1 for row in canonical_contracts if row['is_access_administration']),
        'standard_contracts': sum(1 for row in canonical_contracts if not row['is_access_administration']),
        'drift_count': len(drift_contracts),
        'missing_count': sum(1 for row in contracts if row['state_key'] == 'missing'),
        'metadata_drift_count': sum(1 for row in contracts if row['state_key'] == 'metadata_drift'),
        'database_only_count': sum(1 for row in contracts if row['state_key'] == 'database_only'),
        'database_only_in_use_count': database_only_in_use_count,
        'posture_label': 'Synchronized' if not drift_contracts else 'Review Required',
        'posture_tone': 'normal' if not drift_contracts else 'warning',
    }


def build_permission_registry_snapshot() -> dict[str, Any]:
    canonical_by_key = {
        key: {'key': key, 'module': module, 'action': action, 'description': description}
        for key, module, action, description in DEFAULT_PERMISSIONS
    }
    database_permissions = Permission.query.order_by(Permission.key.asc()).all()
    database_by_key = {permission.key: permission for permission in database_permissions}
    roles = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    inverse_dependencies = _inverse_dependencies()

    roles_by_permission_key = _roles_by_permission_key(roles)
    enabled_jit_providers_by_role = _enabled_jit_providers_by_role()

    role_usage_by_id = {
        int(role.id): _role_impact(
            [role],
            enabled_jit_providers_by_role=enabled_jit_providers_by_role,
        )
        for role in roles
    }

    contracts = [
        _build_contract_row(
            key=key,
            canonical=canonical,
            database_permission=database_by_key.get(key),
            roles=roles_by_permission_key.get(key, []),
            inverse_dependencies=inverse_dependencies,
            enabled_jit_providers_by_role=enabled_jit_providers_by_role,
        )
        for key, canonical in canonical_by_key.items()
    ]
    contracts.extend(
        _build_contract_row(
            key=key,
            canonical=None,
            database_permission=database_permission,
            roles=roles_by_permission_key.get(key, []),
            inverse_dependencies=inverse_dependencies,
            enabled_jit_providers_by_role=enabled_jit_providers_by_role,
        )
        for key, database_permission in database_by_key.items()
        if key not in canonical_by_key
    )
    contracts.sort(key=lambda row: (row['module_label'].lower(), row['title'].lower(), row['key']))

    canonical_contracts = [row for row in contracts if row['code_owned']]
    drift_contracts = [row for row in contracts if row['state_key'] != 'canonical']
    database_only_in_use = [row for row in contracts if row['state_key'] == 'database_only' and row['role_count'] > 0]
    role_mappings = sum(len(role.permissions) for role in roles)
    unused_contracts = sum(1 for row in canonical_contracts if row['role_count'] == 0)
    modules = sorted({row['module'] for row in contracts}, key=module_label)

    return {
        'contracts': contracts,
        'contract_by_key': {row['key']: row for row in contracts},
        'roles': roles,
        'role_usage_by_id': role_usage_by_id,
        'summary': summary,
        'module_options': [{'key': module, 'label': module_label(module)} for module in modules],
    }
