from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_background_progress_uses_shared_operational_toast_contract() -> None:
    shared = read('app/templates/components/operational_progress_toast.html')
    assert 'components/progress_bar.html' in shared
    assert 'progress_bar.determinate' in shared
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
        'app/templates/notifications/partials/_notification_deck_oob.html',
    ):
        source = read(relative)
        assert 'notification-bell-badge' in source
        assert 'rounded-md bg-status-critical' in source
        assert 'rounded-full bg-status-critical' not in source


def test_semantic_attention_and_storage_states_use_operational_callout() -> None:
    for relative in (
        'app/templates/notifications/partials/_center_page_content.html',
        'app/templates/notifications/partials/_notification_deck_notifications.html',
        'app/templates/reports/storage/index.html',
    ):
        source = read(relative)
        assert 'components/operational_callout.html' in source
        assert 'border-status-warning-border' not in source

    storage = read('app/templates/reports/storage/index.html')
    assert "operational_callout.semantic_border_classes('warning')" in storage
    assert 'aria-labelledby="report-storage-connectivity-title"' in storage
    assert 'id="report-storage-connectivity-title"' in storage
    assert 'Retry Connection' in storage
    assert "url_for('reports.storage', verify='1'" in storage


def test_operational_callout_owns_semantic_action_and_supporting_content() -> None:
    source = read('app/templates/components/operational_callout.html')
    assert 'action_href=None' in source
    assert 'action_label=None' in source
    assert 'caller is defined' in source
    assert 'focus-visible:ring-outline-focus' in source
