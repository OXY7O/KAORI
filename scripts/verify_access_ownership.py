#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        raise AssertionError(f'missing required file: {path}')
    return target.read_text()


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f'{label}: missing {needle!r}')


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f'{label}: forbidden {needle!r}')


def main() -> None:
    access_init = read('app/access/__init__.py')
    bootstrap = read('app/bootstrap/blueprints.py')
    settings_routes = read('app/settings/routes.py')
    settings_init = read('app/settings/__init__.py')
    navigation = read('app/common/navigation.py')
    sidebar = read('app/templates/components/navigation/access_management_menu.html')
    welcome = read('app/welcome/shortcuts.py')
    rbac_notifications = read('app/rbac/notifications.py')

    for path in (
        'app/access/overview/routes.py',
        'app/access/overview/presentation.py',
        'app/access/roles/routes.py',
        'app/access/roles/forms.py',
        'app/access/roles/service.py',
        'app/access/roles/presentation.py',
        'app/access/permissions/routes.py',
        'app/access/permissions/presentation.py',
        'app/templates/access/overview/index.html',
        'app/templates/access/roles/index.html',
        'app/templates/access/roles/form.html',
        'app/templates/access/permissions/index.html',
        'app/settings/access_compat.py',
    ):
        if not (ROOT / path).exists():
            raise AssertionError(f'missing Access ownership file: {path}')

    for legacy in (
        'app/settings/roles',
        'app/templates/settings/roles',
        'app/templates/settings/permissions',
    ):
        if (ROOT / legacy).exists():
            raise AssertionError(f'legacy Settings ownership must be removed: {legacy}')

    require(access_init, "url_prefix='/access'", 'Access blueprint')
    require(access_init, "url_prefix='/roles'", 'Roles blueprint registration')
    require(access_init, "url_prefix='/permissions'", 'Permissions blueprint registration')
    require(bootstrap, 'from app.access import bp as access_bp', 'Blueprint bootstrap')
    require(bootstrap, 'access_bp,', 'Blueprint registration')

    forbid(settings_routes, "@bp.route('/roles')", 'Settings routes')
    forbid(settings_routes, "@bp.route('/permissions')", 'Settings routes')
    require(settings_init, 'access_compat_bp', 'Settings compatibility registration')

    for endpoint in (
        'access.overview.index',
        'access.roles.index',
        'access.permissions.index',
    ):
        require(navigation, endpoint, 'Breadcrumb navigation')
        require(sidebar, endpoint, 'Access sidebar')

    require(sidebar, 'Identity Providers', 'Access sidebar')
    require(sidebar, 'Activity Audit', 'Access sidebar')
    require(welcome, "('users.view', 'access.overview.index')", 'Welcome shortcut')
    require(welcome, "('roles.view', 'access.overview.index')", 'Welcome shortcut')
    require(rbac_notifications, "url_for('access.roles.index')", 'RBAC feedback action')

    print('KAORI Access ownership baseline v1 passed')


if __name__ == '__main__':
    main()
