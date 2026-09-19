from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.access.permissions.service import build_permission_registry_snapshot, module_label
from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window, normalize_per_page, positive_int

PERMISSION_VIEW_OPTIONS = ('registry', 'coverage')
PERMISSION_COVERAGE_OPTIONS = ('all', 'mapped', 'unassigned', 'drift')
PERMISSION_DELEGATION_OPTIONS = ('all', 'standard', 'access_admin')
ROLE_TYPE_OPTIONS = ('all', 'system', 'custom')
ROLE_STATE_OPTIONS = ('all', 'active', 'inactive')


def normalize_permission_filters(args: Mapping[str, str | None]) -> dict[str, Any]:
    view = (args.get('view') or 'registry').strip().lower()
    coverage = (args.get('coverage') or 'all').strip().lower()
    delegation = (args.get('delegation') or 'all').strip().lower()
    role_type = (args.get('role_type') or 'all').strip().lower()
    role_state = (args.get('role_state') or 'all').strip().lower()
    return {
        'view': view if view in PERMISSION_VIEW_OPTIONS else 'registry',
        'search': (args.get('search') or '').strip(),
        'module': (args.get('module') or 'all').strip().lower(),
        'coverage': coverage if coverage in PERMISSION_COVERAGE_OPTIONS else 'all',
        'delegation': delegation if delegation in PERMISSION_DELEGATION_OPTIONS else 'all',
        'role_type': role_type if role_type in ROLE_TYPE_OPTIONS else 'all',
        'role_state': role_state if role_state in ROLE_STATE_OPTIONS else 'all',
        'page': positive_int(args.get('page'), 1),
        'per_page': normalize_per_page(args.get('per_page')),
    }


def _contract_matches(contract: Mapping[str, Any], *, search: str, module: str) -> bool:
    if module != 'all' and contract['module'] != module:
        return False
    if not search:
        return True
    term = search.lower()
    haystack = ' '.join(
        str(value or '')
        for value in (
            contract['key'],
            contract['title'],
            contract['module_label'],
            contract['action'],
            contract['description'],
        )
    ).lower()
    return term in haystack


def _registry_rows(contracts: list[dict[str, Any]], filters: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in contracts if _contract_matches(row, search=filters['search'], module=filters['module'])]
    coverage = filters['coverage']
    if coverage == 'mapped':
        rows = [row for row in rows if row['role_count'] > 0]
    elif coverage == 'unassigned':
        rows = [row for row in rows if row['role_count'] == 0]
    elif coverage == 'drift':
        rows = [row for row in rows if row['state_key'] != 'canonical']
    delegation = filters['delegation']
    if delegation != 'all':
        rows = [row for row in rows if row['delegation_tier_key'] == delegation]
    return rows


def _coverage_roles(roles: list[Any], filters: Mapping[str, Any]) -> list[Any]:
    filtered = list(roles)
    if filters['role_type'] == 'system':
        filtered = [role for role in filtered if role.is_system]
    elif filters['role_type'] == 'custom':
        filtered = [role for role in filtered if not role.is_system]
    if filters['role_state'] == 'active':
        filtered = [role for role in filtered if role.is_active]
    elif filters['role_state'] == 'inactive':
        filtered = [role for role in filtered if not role.is_active]
    return filtered


def build_permission_catalog_context(filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_permission_filters(filters or {})
    snapshot = build_permission_registry_snapshot()
    contracts = snapshot['contracts']
    roles = snapshot['roles']

    registry_matches = _registry_rows(contracts, normalized)
    registry_pagination = build_pagination_window(
        total_items=len(registry_matches),
        page=normalized['page'],
        per_page=normalized['per_page'],
    )
    registry_rows = registry_matches[
        registry_pagination.offset : registry_pagination.offset + registry_pagination.per_page
    ]

    coverage_matches = [
        row for row in contracts if _contract_matches(row, search=normalized['search'], module=normalized['module'])
    ]
    if normalized['delegation'] != 'all':
        coverage_matches = [row for row in coverage_matches if row['delegation_tier_key'] == normalized['delegation']]
    coverage_pagination = build_pagination_window(
        total_items=len(coverage_matches),
        page=normalized['page'],
        per_page=normalized['per_page'],
    )
    coverage_rows = coverage_matches[
        coverage_pagination.offset : coverage_pagination.offset + coverage_pagination.per_page
    ]
    coverage_roles = _coverage_roles(roles, normalized)
    role_permission_keys = {role.id: role.permission_keys() for role in coverage_roles}

    active_pagination = coverage_pagination if normalized['view'] == 'coverage' else registry_pagination
    matching_count = len(coverage_matches) if normalized['view'] == 'coverage' else len(registry_matches)

    return {
        'active_view': normalized['view'],
        'summary': snapshot['summary'],
        'module_options': snapshot['module_options'],
        'roles': roles,
        'registry_rows': registry_rows,
        'coverage_rows': coverage_rows,
        'coverage_roles': coverage_roles,
        'role_permission_keys': role_permission_keys,
        'matching_count': matching_count,
        'filters': {
            **normalized,
            'page': active_pagination.page,
            'per_page': active_pagination.per_page,
        },
        'pagination': active_pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'pagination_query': {
            'view': normalized['view'],
            'search': normalized['search'],
            'module': normalized['module'],
            'coverage': normalized['coverage'],
            'delegation': normalized['delegation'],
            'role_type': normalized['role_type'],
            'role_state': normalized['role_state'],
            'per_page': active_pagination.per_page,
        },
    }


def build_permission_detail_context(permission_key: str) -> dict[str, Any] | None:
    snapshot = build_permission_registry_snapshot()
    contract = snapshot['contract_by_key'].get(permission_key)
    if contract is None:
        return None

    contracts_by_key = snapshot['contract_by_key']
    requires = [
        {
            'key': key,
            'title': contracts_by_key.get(key, {}).get('title') or key,
            'module_label': contracts_by_key.get(key, {}).get('module_label') or '-',
        }
        for key in contract['requires']
    ]
    effective_requires = [
        {
            'key': key,
            'title': contracts_by_key.get(key, {}).get('title') or key,
            'module_label': contracts_by_key.get(key, {}).get('module_label') or '-',
        }
        for key in contract['effective_requires']
    ]
    required_by = [
        {
            'key': key,
            'title': contracts_by_key.get(key, {}).get('title') or key,
            'module_label': contracts_by_key.get(key, {}).get('module_label') or '-',
        }
        for key in contract['required_by']
    ]
    role_usage_by_id = snapshot['role_usage_by_id']
    role_rows = [
        {
            'id': role.id,
            'name': role.display_name,
            'key': role.name,
            'type_label': 'Default' if role.is_system else 'Custom',
            'type_icon': 'shield-check' if role.is_system else 'user-cog',
            'state_label': 'Active' if role.is_active else 'Inactive',
            'state_tone': 'normal' if role.is_active else 'unknown',
            'active_user_count': role_usage_by_id.get(int(role.id), {}).get('active_user_count', 0),
            'jit_provider_count': role_usage_by_id.get(int(role.id), {}).get('jit_provider_count', 0),
        }
        for role in contract['roles']
    ]

    return {
        'permission': contract,
        'requires': requires,
        'effective_requires': effective_requires,
        'required_by': required_by,
        'role_rows': role_rows,
        'summary': snapshot['summary'],
        'module_label': module_label(contract['module']),
    }
