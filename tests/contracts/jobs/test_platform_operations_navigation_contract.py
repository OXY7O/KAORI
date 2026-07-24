from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_inventory_sync_is_grouped_with_jobs_and_not_settings() -> None:
    platform_menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()
    settings_menu = (ROOT / 'app/templates/components/navigation/settings_menu.html').read_text()
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text()

    assert 'Platform Operations' in platform_menu
    assert 'Jobs &amp; Executions' in platform_menu
    assert 'Inventory Sync' in platform_menu
    assert "url_for('settings.inventory_sync.index')" in platform_menu
    assert 'Inventory Sync' not in settings_menu
    assert "current_user.has_permission('settings.manage_integrations')" in sidebar


def test_unused_report_settings_surface_is_retired() -> None:
    routes = (ROOT / 'app/settings/routes.py').read_text()
    settings_menu = (ROOT / 'app/templates/components/navigation/settings_menu.html').read_text()
    navigation = (ROOT / 'app/common/navigation.py').read_text()

    assert "@bp.route('/reports')" not in routes
    assert 'settings.reports' not in settings_menu
    assert "'settings.reports'" not in navigation
