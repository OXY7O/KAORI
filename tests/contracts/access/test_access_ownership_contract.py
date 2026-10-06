from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def legacy_files(path: str) -> list[Path]:
    target = ROOT / path
    if target.is_file():
        return [target]
    if not target.is_dir():
        return []
    return [item for item in target.rglob('*') if item.is_file()]


def test_access_owns_roles_permissions_and_overview() -> None:
    bootstrap = read('app/bootstrap/blueprints.py')
    access_init = read('app/access/__init__.py')
    assert 'from app.access import bp as access_bp' in bootstrap
    assert 'access_bp,' in bootstrap
    assert "url_prefix='/access'" in access_init
    assert "url_prefix='/roles'" in access_init
    assert "url_prefix='/permissions'" in access_init


def test_settings_has_no_access_compatibility_routes_or_shim() -> None:
    settings_routes = read('app/settings/routes.py')
    settings_init = read('app/settings/__init__.py')
    assert not (ROOT / 'app/settings/access_compat.py').exists()
    for forbidden in (
        "@bp.route('/roles')",
        "@bp.route('/permissions')",
        "@bp.get('/roles')",
        "@bp.get('/permissions')",
        'access_compat',
        '/settings/roles',
        '/settings/permissions',
    ):
        assert forbidden not in settings_routes
        assert forbidden not in settings_init


def test_settings_role_permission_legacy_files_are_removed() -> None:
    # Filesystem patch tools can leave empty parent directories behind. The contract
    # guards code ownership: no legacy file may remain under these Settings paths.
    assert legacy_files('app/settings/roles') == []
    assert legacy_files('app/templates/settings/roles') == []
    assert legacy_files('app/templates/settings/permissions') == []
    assert (ROOT / 'app/access/roles/forms.py').exists()
    assert (ROOT / 'app/templates/access/roles/index.html').exists()
    assert (ROOT / 'app/templates/access/permissions/index.html').exists()


def test_access_navigation_uses_canonical_endpoints() -> None:
    sidebar = read('app/templates/components/navigation/access_management_menu.html')
    navigation = read('app/common/navigation.py')
    welcome = read('app/welcome/shortcuts.py')
    for endpoint in ('access.overview.index', 'access.roles.index', 'access.permissions.index'):
        assert endpoint in sidebar
        assert endpoint in navigation
    assert 'Identity Providers' in sidebar
    assert 'Activity Audit' in sidebar
    assert "('users.view', 'access.overview.index')" in welcome
    assert "('roles.view', 'access.overview.index')" in welcome


def test_no_access_legacy_route_references_remain_in_runtime_code() -> None:
    forbidden = (
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
    for target in (ROOT / 'app').rglob('*'):
        if not target.is_file() or target.suffix not in {'.py', '.html'}:
            continue
        text = target.read_text(errors='ignore')
        for token in forbidden:
            assert token not in text, f'{target.relative_to(ROOT)} contains {token!r}'


def test_access_ui_is_final_locked_after_child_page_review() -> None:
    readme = read('app/access/README.md')
    assert 'Access v1 is final-locked' in readme
    assert 'verify_access_final_lock.py' in readme
    assert 'redirect shims' in readme
    assert 'Legacy Settings role/permission URLs are retired' in readme
