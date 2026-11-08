from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_platform_operations_section_contains_operations_center_and_integrations_as_sibling_roots() -> None:
    catalog = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text()
    page = (ROOT / 'app/templates/platform_operations/jobs/index.html').read_text()

    operations_start = catalog.index("key='operations_center'")
    integrations_start = catalog.index("key='integrations'")
    assert operations_start < integrations_start
    operations = catalog[operations_start:integrations_start]
    integrations = catalog[integrations_start:]

    assert "label='Operations Center'" in operations
    assert "section='Platform'" in operations
    assert "'overview'" in operations
    assert "'jobs', 'Jobs'" in operations
    assert "'data_lifecycle'" in operations
    assert "'kubernetes_admin'" in operations
    assert "'platform_operations.overview.index'" in operations
    assert "'jobs.executions'" in operations
    assert "'platform_operations.data_lifecycle.index'" in operations
    assert "'platform_operations.kubernetes.index'" in operations
    assert 'Notification Channels' not in operations

    assert "label='Integrations'" in integrations
    assert "section='Platform'" in integrations
    assert "'integrations.overview'" in integrations
    assert "'notification_channels.index'" in integrations
    assert 'Notification Channels' in integrations

    assert 'Job Configuration' in page
    assert "url_for('jobs.configuration')" in page


def test_secret_reveal_administration_is_not_owned_by_settings_navigation() -> None:
    catalog = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text()
    settings_start = catalog.index("key='settings'")
    settings = catalog[settings_start:]

    assert 'settings.secret_reveal' not in settings
    assert 'Secret Reveal' not in settings
    assert "'platform_operations.kubernetes.index'" in catalog
