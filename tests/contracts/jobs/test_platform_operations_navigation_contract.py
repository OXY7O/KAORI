from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_platform_operations_groups_jobs_and_inventory_sync_as_submenu() -> None:
    menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()

    assert '<details class="sidebar-menu space-y-1"' in menu
    assert 'Platform Operations' in menu
    assert 'Jobs &amp; Executions' in menu
    assert 'Inventory Sync' in menu
    assert 'sidebar-submenu' in menu
    assert "current_user.has_permission('jobs.view')" in menu
    assert "current_user.has_permission('settings.manage_integrations')" in menu
