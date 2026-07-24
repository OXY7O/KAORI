from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_platform_operations_uses_one_jobs_submenu_and_configuration_tab() -> None:
    menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()
    page = (ROOT / 'app/templates/jobs/index.html').read_text()

    assert '<details' in menu
    assert 'Platform Operations' in menu
    assert 'Jobs &amp; Executions' in menu
    assert 'Inventory Sync' not in menu
    assert "url_for('jobs.executions')" in menu
    assert 'Job Configuration' in page
    assert "url_for('jobs.configuration')" in page
