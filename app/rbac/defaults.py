from __future__ import annotations

from collections.abc import Mapping

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple, unique_by


def _validate_permission_dependencies(
    dependencies: Mapping[str, set[str]],
    permission_keys: set[str],
) -> None:
    for permission_key, required_keys in dependencies.items():
        if permission_key not in permission_keys:
            raise DefinitionError(f'permission_dependencies references unknown permission {permission_key!r}.')
        unknown = sorted(required_keys - permission_keys)
        if unknown:
            raise DefinitionError(
                f'permission_dependencies.{permission_key} references unknown permissions: {", ".join(unknown)}.'
            )
        if permission_key in required_keys:
            raise DefinitionError(f'permission_dependencies.{permission_key} cannot depend on itself.')

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(permission_key: str, trail: tuple[str, ...]) -> None:
        if permission_key in visited:
            return
        if permission_key in visiting:
            cycle = ' -> '.join((*trail, permission_key))
            raise DefinitionError(f'Permission dependency cycle detected: {cycle}.')
        visiting.add(permission_key)
        for dependency_key in sorted(dependencies.get(permission_key, set())):
            visit(dependency_key, (*trail, permission_key))
        visiting.remove(permission_key)
        visited.add(permission_key)

    for permission_key in sorted(dependencies):
        visit(permission_key, ())


def _load_access_defaults() -> tuple[
    list[tuple[str, str, str, str]],
    dict[str, str],
    dict[str, set[str]],
    set[str],
    dict[str, dict[str, str]],
    dict[str, set[str]],
]:
    document = load_definition_document('rbac/access.yaml', expected_kind='rbac_access')
    raw_modules = [
        require_mapping(item, f'control_modules[{index}]')
        for index, item in enumerate(require_list(document.get('control_modules'), 'control_modules'))
    ]
    unique_by(raw_modules, 'key', 'control_modules')
    permission_module_labels = {
        require_str(item, 'key', f'control_modules[{index}]'): require_str(item, 'label', f'control_modules[{index}]')
        for index, item in enumerate(raw_modules)
    }
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
    permission_modules = {item[1] for item in permissions}
    unknown_modules = sorted(permission_modules - set(permission_module_labels))
    if unknown_modules:
        raise DefinitionError('permissions reference unknown control modules: ' + ', '.join(unknown_modules) + '.')
    unused_modules = sorted(set(permission_module_labels) - permission_modules)
    if unused_modules:
        raise DefinitionError('control_modules contains unused module definitions: ' + ', '.join(unused_modules) + '.')

    raw_dependencies = require_mapping(document.get('permission_dependencies') or {}, 'permission_dependencies')
    permission_dependencies: dict[str, set[str]] = {}
    for raw_key, raw_requires in raw_dependencies.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise DefinitionError('permission_dependencies keys must be non-empty strings.')
        permission_key = raw_key.strip()
        permission_dependencies[permission_key] = set(
            string_tuple(raw_requires, f'permission_dependencies.{permission_key}')
        )
    _validate_permission_dependencies(permission_dependencies, permission_keys)

    access_administration_permissions = set(
        string_tuple(document.get('access_administration_permissions'), 'access_administration_permissions')
    )
    unknown_administration_permissions = sorted(access_administration_permissions - permission_keys)
    if unknown_administration_permissions:
        raise DefinitionError(
            'access_administration_permissions references unknown permissions: '
            + ', '.join(unknown_administration_permissions)
            + '.'
        )
    if not access_administration_permissions:
        raise DefinitionError('access_administration_permissions must contain at least one permission.')

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
    return (
        permissions,
        permission_module_labels,
        permission_dependencies,
        access_administration_permissions,
        role_definitions,
        role_permissions,
    )


(
    DEFAULT_PERMISSIONS,
    PERMISSION_MODULE_LABELS,
    DEFAULT_PERMISSION_DEPENDENCIES,
    ACCESS_ADMINISTRATION_PERMISSIONS,
    DEFAULT_ROLE_DEFINITIONS,
    DEFAULT_ROLE_PERMISSIONS,
) = _load_access_defaults()
