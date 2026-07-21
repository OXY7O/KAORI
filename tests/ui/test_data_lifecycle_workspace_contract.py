from pathlib import Path


def test_data_lifecycle_has_dedicated_settings_navigation() -> None:
    menu = Path('app/templates/components/navigation/settings_menu.html').read_text(encoding='utf-8')
    activity = Path('app/templates/notifications/activity.html').read_text(encoding='utf-8')
    assert "url_for('settings.data_lifecycle.index')" in menu
    assert 'Data Lifecycle' in menu
    assert 'Retention' not in activity or 'Retention moved:' in activity
    assert 'activity-audit-tab-retention' not in activity
    assert 'Settings → Data Lifecycle' in activity


def test_data_lifecycle_workspace_scales_by_domain_not_page() -> None:
    page = Path('app/templates/settings/data_lifecycle/index.html').read_text(encoding='utf-8')
    policy = Path('app/templates/settings/data_lifecycle/partials/_domain_workspace.html').read_text(encoding='utf-8')
    history = Path('app/templates/settings/data_lifecycle/partials/_history.html').read_text(encoding='utf-8')
    for label in ('Retention Policies', 'Archive Storage', 'Execution History'):
        assert label in page
    assert 'lifecycle.domains' in page
    assert 'lifecycle.planned_domains' in page
    assert 'Workload-specific hot retention' in policy
    assert 'Preview' in policy
    assert 'Archive & Cleanup' in policy
    assert 'archive_domain' in history
    assert 'All Domains' in history
    assert 'Archives per page' in history
    assert 'Rows per page' not in history


def test_loading_bar_and_table_hierarchy_follow_kaori_contract() -> None:
    policy = Path('app/templates/settings/data_lifecycle/partials/_domain_workspace.html').read_text(encoding='utf-8')
    history = Path('app/templates/settings/data_lifecycle/partials/_history.html').read_text(encoding='utf-8')
    assert policy.index('table_ui.block_header_classes()') < policy.index('table_ui.loading_bar_classes()')
    assert history.index('table_ui.block_header_classes()') < history.index('table_ui.loading_bar_classes()')
    assert 'table_ui.title_cell' in history
    assert 'text-right' not in history or 'header_cell_classes(true)' in history
