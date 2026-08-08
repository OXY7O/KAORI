from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_access_owns_roles_permissions_and_overview() -> None:
    bootstrap = read('app/bootstrap/blueprints.py')
    access_init = read('app/access/__init__.py')
    assert 'from app.access import bp as access_bp' in bootstrap
    assert 'access_bp,' in bootstrap
    assert "url_prefix='/access'" in access_init
    assert "url_prefix='/roles'" in access_init
    assert "url_prefix='/permissions'" in access_init


def test_settings_keeps_redirect_only_compatibility() -> None:
    settings_routes = read('app/settings/routes.py')
    compat = read('app/settings/access_compat.py')
    assert "@bp.route('/roles')" not in settings_routes
    assert "@bp.route('/permissions')" not in settings_routes
    assert "access.roles.index" in compat
    assert "access.permissions.index" in compat
    assert '308 if request.method != \'GET\' else 302' in compat


def test_settings_role_templates_and_forms_are_removed() -> None:
    assert not (ROOT / 'app/settings/roles').exists()
    assert not (ROOT / 'app/templates/settings/roles').exists()
    assert not (ROOT / 'app/templates/settings/permissions').exists()
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


def test_access_ui_is_not_final_locked_by_this_refactor() -> None:
    readme = read('app/access/README.md')
    assert 'not the Access UI Final Lock' in readme
    assert 'reviewed independently' in readme
