from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models import Permission, Role
from app.rbac.defaults import DEFAULT_PERMISSIONS
from app.rbac.service import PERMISSION_DEPENDENCIES

MODULE_LABELS: dict[str, str] = {
    'workspace': 'Welcome',
    'k8s_dashboard': 'K8s Dashboard',
    'k8s_cluster': 'K8s Cluster',
    'k8s_inventory': 'K8s Inventory',
    'k8s_analytics': 'K8s Analytics',
    'k8s_operations': 'K8s Operations',
    'governance': 'K8s Governance',
    'integrations': 'Integrations',
    'platform_operations': 'Platform Operations',
    'reports': 'Reports',
    'intelligence': 'Intelligence',
    'knowledge': 'Knowledge',
    'access': 'Access',
    'settings': 'Settings',
    'system': 'System',
}

REGISTRY_STATE_PRESENTATION: dict[str, dict[str, str]] = {
    'canonical': {'label': 'Canonical', 'tone': 'normal', 'icon': 'circle-check'},
    'missing': {'label': 'Missing From Registry', 'tone': 'warning', 'icon': 'database-zap'},
    'metadata_drift': {'label': 'Metadata Drift', 'tone': 'warning', 'icon': 'triangle-alert'},
    'database_only': {'label': 'Database Only', 'tone': 'warning', 'icon': 'database'},
}


def module_label(value: str | None) -> str:
    key = (value or 'general').strip().lower()
    return MODULE_LABELS.get(key, key.replace('_', ' ').title())


def action_label(value: str | None) -> str:
    return (value or 'view').replace('_', ' ').title()


def permission_title(key: str, action: str | None) -> str:
    return action_label(action or key.rsplit('.', 1)[-1])


def _inverse_dependencies() -> dict[str, set[str]]:
    inverse: dict[str, set[str]] = defaultdict(set)
    for permission_key, dependencies in PERMISSION_DEPENDENCIES.items():
        for dependency_key in dependencies:
            inverse[dependency_key].add(permission_key)
    return dict(inverse)


def build_permission_registry_snapshot() -> dict[str, Any]:
    canonical_by_key = {
        key: {
            'key': key,
            'module': module,
            'action': action,
            'description': description,
        }
        for key, module, action, description in DEFAULT_PERMISSIONS
    }
    database_permissions = Permission.query.order_by(Permission.key.asc()).all()
    database_by_key = {permission.key: permission for permission in database_permissions}
    roles = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    inverse_dependencies = _inverse_dependencies()

    roles_by_permission_key: dict[str, list[Role]] = defaultdict(list)
    for role in roles:
        for permission in role.permissions:
            roles_by_permission_key[permission.key].append(role)

    contracts: list[dict[str, Any]] = []
    for key, canonical in canonical_by_key.items():
        database_permission = database_by_key.get(key)
        if database_permission is None:
            state_key = 'missing'
        elif (
            database_permission.module != canonical['module']
            or database_permission.action != canonical['action']
            or (database_permission.description or '') != (canonical['description'] or '')
        ):
            state_key = 'metadata_drift'
        else:
            state_key = 'canonical'

        mapped_roles = roles_by_permission_key.get(key, [])
        contracts.append(
            {
                **canonical,
                'title': permission_title(key, canonical['action']),
                'module_label': module_label(canonical['module']),
                'database_id': database_permission.id if database_permission else None,
                'database_module': database_permission.module if database_permission else None,
                'database_action': database_permission.action if database_permission else None,
                'database_description': database_permission.description if database_permission else None,
                'created_at': database_permission.created_at if database_permission else None,
                'state_key': state_key,
                'state': REGISTRY_STATE_PRESENTATION[state_key],
                'code_owned': True,
                'requires': sorted(PERMISSION_DEPENDENCIES.get(key, set())),
                'required_by': sorted(inverse_dependencies.get(key, set())),
                'roles': mapped_roles,
                'role_count': len(mapped_roles),
            }
        )

    for key, database_permission in database_by_key.items():
        if key in canonical_by_key:
            continue
        mapped_roles = roles_by_permission_key.get(key, [])
        state_key = 'database_only'
        contracts.append(
            {
                'key': key,
                'module': database_permission.module,
                'action': database_permission.action,
                'description': database_permission.description,
                'title': permission_title(key, database_permission.action),
                'module_label': module_label(database_permission.module),
                'database_id': database_permission.id,
                'database_module': database_permission.module,
                'database_action': database_permission.action,
                'database_description': database_permission.description,
                'created_at': database_permission.created_at,
                'state_key': state_key,
                'state': REGISTRY_STATE_PRESENTATION[state_key],
                'code_owned': False,
                'requires': sorted(PERMISSION_DEPENDENCIES.get(key, set())),
                'required_by': sorted(inverse_dependencies.get(key, set())),
                'roles': mapped_roles,
                'role_count': len(mapped_roles),
            }
        )

    contracts.sort(key=lambda row: (row['module_label'].lower(), row['title'].lower(), row['key']))

    canonical_contracts = [row for row in contracts if row['code_owned']]
    drift_contracts = [row for row in contracts if row['state_key'] != 'canonical']
    role_mappings = sum(len(role.permissions) for role in roles)
    unused_contracts = sum(1 for row in canonical_contracts if row['role_count'] == 0)
    modules = sorted({row['module'] for row in contracts}, key=module_label)

    return {
        'contracts': contracts,
        'contract_by_key': {row['key']: row for row in contracts},
        'roles': roles,
        'summary': {
            'canonical_permissions': len(canonical_contracts),
            'registered_permissions': len(database_permissions),
            'control_modules': len(modules),
            'role_mappings': role_mappings,
            'unused_contracts': unused_contracts,
            'drift_count': len(drift_contracts),
            'missing_count': sum(1 for row in contracts if row['state_key'] == 'missing'),
            'metadata_drift_count': sum(1 for row in contracts if row['state_key'] == 'metadata_drift'),
            'database_only_count': sum(1 for row in contracts if row['state_key'] == 'database_only'),
            'posture_label': 'Synchronized' if not drift_contracts else 'Review Required',
            'posture_tone': 'normal' if not drift_contracts else 'warning',
        },
        'module_options': [
            {'key': module, 'label': module_label(module)}
            for module in modules
        ],
    }
