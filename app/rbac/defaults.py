from __future__ import annotations

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple, unique_by


def _load_access_defaults() -> tuple[
    list[tuple[str, str, str, str]],
    dict[str, dict[str, str]],
    dict[str, set[str]],
]:
    document = load_definition_document('rbac/access.yaml', expected_kind='rbac_access')
    raw_permissions = [
        require_mapping(item, f'permissions[{index}]')
        for index, item in enumerate(require_list(document.get('permissions'), 'permissions'))
    ]
    unique_by(raw_permissions, 'key', 'permissions')
    permissions = [
        (
            require_str(item, 'key', f'permissions[{index}]'),
            require_str(item, 'module', f'permissions[{index}]'),
            require_str(item, 'action', f'permissions[{index}]'),
            require_str(item, 'description', f'permissions[{index}]'),
        )
        for index, item in enumerate(raw_permissions)
    ]
    permission_keys = {item[0] for item in permissions}

    raw_roles = [
        require_mapping(item, f'system_roles[{index}]')
        for index, item in enumerate(require_list(document.get('system_roles'), 'system_roles'))
    ]
    unique_by(raw_roles, 'key', 'system_roles')
    role_definitions: dict[str, dict[str, str]] = {}
    role_permissions: dict[str, set[str]] = {}
    for index, item in enumerate(raw_roles):
        path = f'system_roles[{index}]'
        key = require_str(item, 'key', path)
        role_definitions[key] = {
            'display_name': require_str(item, 'display_name', path),
            'description': require_str(item, 'description', path),
        }
        grants = set(string_tuple(item.get('permissions'), f'{path}.permissions'))
        unknown = sorted(grants - permission_keys)
        if unknown:
            raise DefinitionError(f'{path} references unknown permissions: {", ".join(unknown)}.')
        role_permissions[key] = grants
    return permissions, role_definitions, role_permissions


DEFAULT_PERMISSIONS, DEFAULT_ROLE_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS = _load_access_defaults()
