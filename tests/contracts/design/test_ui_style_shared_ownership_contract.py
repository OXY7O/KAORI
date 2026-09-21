from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_background_progress_uses_shared_operational_toast_contract() -> None:
    shared = read('app/templates/components/operational_progress_toast.html')
    assert 'components/progress_bar.html' in shared
    assert 'progress_bar.notification_progress' in shared
    assert 'progress_bar.notification_indeterminate' in shared
    assert 'progress_bar.determinate' not in shared
    assert 'data-operational-toast' in shared

    for relative in (
        'app/templates/components/navigation/_individual_sync_status.html',
        'app/templates/components/navigation/_quick_sync_status.html',
    ):
        source = read(relative)
        assert 'components/operational_progress_toast.html' in source
        assert 'progress_toast.render' in source
        assert 'components/activity_status_card.html' not in source


def test_notification_badges_follow_rectangular_kaori_label_geometry() -> None:
    for relative in (
        'app/templates/components/navigation/_notification_center.html',
        'app/templates/platform_operations/notifications/partials/_notification_deck_oob.html',
    ):
        source = read(relative)
        assert 'notification-bell-badge' in source
        assert 'rounded-md bg-status-critical' in source
        assert 'rounded-full bg-status-critical' not in source


def test_semantic_attention_and_storage_states_use_operational_callout() -> None:
    for relative in (
        'app/templates/platform_operations/notifications/partials/_center_page_content.html',
        'app/templates/platform_operations/notifications/partials/_notification_deck_notifications.html',
        'app/templates/reports/storage/index.html',
    ):
        source = read(relative)
        assert 'components/operational_callout.html' in source
        assert 'border-status-warning-border' not in source

    storage = read('app/templates/reports/storage/index.html')
    assert "operational_callout.semantic_border_classes('warning')" in storage
    assert 'aria-labelledby="report-storage-connectivity-title"' in storage
    assert 'id="report-storage-connectivity-title"' in storage
    assert 'Verify Connection' in storage
    assert "url_for('reports.verify_storage')" in storage


def test_operational_callout_owns_semantic_action_and_supporting_content() -> None:
    source = read('app/templates/components/operational_callout.html')
    assert 'action_href=None' in source
    assert 'action_label=None' in source
    assert 'caller is defined' in source
    assert 'focus-visible:ring-outline-focus' in source


def test_reusable_component_ownership_registry_and_framed_tab_delegation() -> None:
    ownership = read('docs/design/components/REUSABLE_COMPONENT_OWNERSHIP.md')
    design_readme = read('docs/design/README.md')
    design_system = read('docs/design/DESIGN_SYSTEM.md')
    adapter = read('app/templates/components/integration_workspace_tabs.html')

    for marker in (
        'Hero and context',
        'Readiness and operational callouts',
        'Tables, filters, loading, empty/error, and pagination',
        'Forms, action bars, and destructive confirmation',
        'Modal, drawer, and sheet surfaces',
        'Navigation and mobile action surfaces',
        'Operational toast and notification surfaces',
        'Framed Workspace Tabs',
        'Adapter rule',
    ):
        assert marker in ownership

    assert 'components/REUSABLE_COMPONENT_OWNERSHIP.md' in design_readme
    assert 'components/REUSABLE_COMPONENT_OWNERSHIP.md' in design_system
    assert 'components/framed_workspace_tabs.html' in adapter
    assert 'components/operational_section_card.html' in adapter
    assert 'framed_workspace_tabs.render(' in adapter
    assert 'operational_section_card.shell_classes()' in adapter
    assert 'role="tablist"' not in adapter
    assert '<button type="button"' not in adapter
