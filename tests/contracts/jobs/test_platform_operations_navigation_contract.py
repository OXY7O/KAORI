from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_platform_operations_contains_jobs_data_lifecycle_and_kubernetes_administration() -> None:
    menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()
    page = (ROOT / 'app/templates/jobs/index.html').read_text()

    assert '<details' in menu
    assert 'Platform Operations' in menu
    assert 'Jobs &amp; Executions' in menu
    assert 'Data Lifecycle' in menu
    assert 'Kubernetes Administration' in menu
    assert "url_for('jobs.executions')" in menu
    assert "url_for('platform_operations.data_lifecycle.index')" in menu
    assert "url_for('platform_operations.kubernetes.index')" in menu
    assert 'Inventory Sync' not in menu
    assert menu.index('Jobs &amp; Executions') < menu.index('Data Lifecycle') < menu.index('Kubernetes Administration')
    assert 'Job Configuration' in page
    assert "url_for('jobs.configuration')" in page


def test_secret_reveal_administration_is_not_owned_by_settings_navigation() -> None:
    settings_menu = (ROOT / 'app/templates/components/navigation/settings_menu.html').read_text()
    platform_menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()

    assert 'settings.secret_reveal' not in settings_menu
    assert 'Secret Reveal' not in settings_menu
    assert 'platform_operations.kubernetes.index' in platform_menu
