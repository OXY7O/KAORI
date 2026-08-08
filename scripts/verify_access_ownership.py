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


def require_no_files(path: str) -> None:
    target = ROOT / path
    if target.is_file():
        raise AssertionError(f'legacy Settings ownership file must be removed: {path}')
    if target.is_dir():
        files = sorted(item.relative_to(ROOT).as_posix() for item in target.rglob('*') if item.is_file())
        if files:
            raise AssertionError(f'legacy Settings ownership files must be removed under {path}: {files}')


def main() -> None:
    access_init = read('app/access/__init__.py')
    bootstrap = read('app/bootstrap/blueprints.py')
    settings_routes = read('app/settings/routes.py')
    settings_init = read('app/settings/__init__.py')
    navigation = read('app/common/navigation.py')
    sidebar = read('app/templates/components/navigation/access_management_menu.html')
    welcome = read('app/welcome/shortcuts.py')
    rbac_notifications = read('app/rbac/notifications.py')
    access_readme = read('app/access/README.md')
    settings_readme = read('app/settings/README.md')
    ownership_doc = read('docs/architecture/ACCESS_OWNERSHIP.md')

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
    ):
        if not (ROOT / path).exists():
            raise AssertionError(f'missing Access ownership file: {path}')

    for legacy in (
        'app/settings/roles',
        'app/templates/settings/roles',
        'app/templates/settings/permissions',
    ):
        require_no_files(legacy)

    if (ROOT / 'app/settings/access_compat.py').exists():
        raise AssertionError('Access compatibility shim must be removed: app/settings/access_compat.py')

    require(access_init, "url_prefix='/access'", 'Access blueprint')
    require(access_init, "url_prefix='/roles'", 'Roles blueprint registration')
    require(access_init, "url_prefix='/permissions'", 'Permissions blueprint registration')
    require(bootstrap, 'from app.access import bp as access_bp', 'Blueprint bootstrap')
    require(bootstrap, 'access_bp,', 'Blueprint registration')

    for forbidden in (
        "@bp.route('/roles')",
        "@bp.route('/permissions')",
        "@bp.get('/roles')",
        "@bp.get('/permissions')",
        'access_compat',
        '/settings/roles',
        '/settings/permissions',
    ):
        forbid(settings_routes, forbidden, 'Settings routes')
        forbid(settings_init, forbidden, 'Settings registration')

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

    for text, label in (
        (access_readme, 'Access README'),
        (settings_readme, 'Settings README'),
        (ownership_doc, 'Access ownership documentation'),
    ):
        forbid(text, 'redirect-only compatibility shims', label)
        forbid(text, 'app/settings/access_compat.py', label)

    forbidden_code_tokens = (
        'settings.access_compat',
        "url_for('settings.roles",
        'url_for("settings.roles',
        "url_for('settings.permission",
        'url_for("settings.permission',
        "'/settings/roles",
        '"/settings/roles',
        "'/settings/permissions",
        '"/settings/permissions',
    )
    for target in sorted((ROOT / 'app').rglob('*')):
        if not target.is_file() or target.suffix not in {'.py', '.html'}:
            continue
        text = target.read_text(errors='ignore')
        for token in forbidden_code_tokens:
            if token in text:
                relative = target.relative_to(ROOT).as_posix()
                raise AssertionError(f'legacy Access compatibility reference in {relative}: {token!r}')

    print('KAORI Access ownership baseline v1.1 passed: canonical Access ownership with legacy Settings role/permission code and compatibility shims removed.')


if __name__ == '__main__':
    main()
