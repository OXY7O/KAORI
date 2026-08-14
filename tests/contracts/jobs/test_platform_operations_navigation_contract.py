from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_platform_operations_section_contains_operations_center_and_integrations_as_sibling_roots() -> None:
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text()
    operations_menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()
    integrations_menu = (ROOT / 'app/templates/components/navigation/integrations_menu.html').read_text()
    page = (ROOT / 'app/templates/jobs/index.html').read_text()

    section = sidebar.split('>Platform Operations</div>', 1)[1].split('>Administration</div>', 1)[0]
    assert 'components/navigation/platform_operations_menu.html' in section
    assert 'components/navigation/integrations_menu.html' in section
    assert section.index('platform_operations_menu.html') < section.index('integrations_menu.html')

    assert '<details' in operations_menu
    assert 'Operations Center' in operations_menu
    assert 'Overview' in operations_menu
    assert 'Jobs &amp; Executions' in operations_menu
    assert 'Data Lifecycle' in operations_menu
    assert 'Kubernetes Administration' in operations_menu
    assert 'Integrations' not in operations_menu
    assert 'Notification Channels' not in operations_menu
    assert "url_for('platform_operations.overview.index')" in operations_menu
    assert "url_for('jobs.executions')" in operations_menu
    assert "url_for('platform_operations.data_lifecycle.index')" in operations_menu
    assert "url_for('platform_operations.kubernetes.index')" in operations_menu
    assert 'Inventory Sync' not in operations_menu

    assert '<details' in integrations_menu
    assert 'Integrations' in integrations_menu
    assert "url_for('integrations.overview')" in integrations_menu
    assert "url_for('notification_channels.index')" in integrations_menu
    assert 'Notification Channels' in integrations_menu

    assert 'Job Configuration' in page
    assert "url_for('jobs.configuration')" in page


def test_secret_reveal_administration_is_not_owned_by_settings_navigation() -> None:
    settings_menu = (ROOT / 'app/templates/components/navigation/settings_menu.html').read_text()
    platform_menu = (ROOT / 'app/templates/components/navigation/platform_operations_menu.html').read_text()

    assert 'settings.secret_reveal' not in settings_menu
    assert 'Secret Reveal' not in settings_menu
    assert 'platform_operations.kubernetes.index' in platform_menu
