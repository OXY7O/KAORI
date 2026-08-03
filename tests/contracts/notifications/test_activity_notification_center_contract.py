from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_topbar_keeps_distinct_activity_and_bell_triggers() -> None:
    template = read('app/templates/components/navigation/_notification_center.html')

    assert 'data-lucide="activity"' in template
    assert 'data-lucide="bell"' in template
    assert "activityCenterTab = 'running'" in template
    assert "activityCenterTab = {{ \"'attention'\" if unread_count else \"'history'\" }}" in template
    assert 'data-activity-count-badge' in template
    assert 'unread_count' in template


def test_drawer_and_full_page_share_one_activity_center_context() -> None:
    routes = read('app/notifications/routes.py')
    service = read('app/notifications/service.py')
    query = read('app/notifications/queries.py')
    page = read('app/templates/notifications/index.html')

    assert 'get_activity_center_context' in service
    assert "@notifications_bp.get('/')" in routes
    assert "'notifications/partials/_center_page_content.html'" in routes
    assert 'activity_center=context' in routes
    assert 'JobExecution.subscribers.any' in query
    assert 'JobExecution.requested_by_user_id == user_id' in query
    assert 'activity_center.active_count' in page
    assert 'activity_center.unread_count' in page


def test_background_progress_uses_activity_center_instead_of_progress_toasts() -> None:
    layout = read('app/templates/layouts/app.html')
    feedback = read('app/notifications/service.py')
    toast = read('app/templates/components/navigation/_quick_sync_result.html')

    assert 'showOperationalProgressToast' not in layout
    assert 'startOperationalActivity' in layout
    assert 'data-local-activity-list' in read(
        'app/templates/components/navigation/_notification_center.html'
    )
    assert "return 'activity_center'" in feedback
    assert "delivery|default('toast') == 'activity_center'" in toast


def test_activity_center_preserves_explicit_read_semantics() -> None:
    component = read('app/templates/notifications/components/_activity_center_items.html')
    routes = read('app/notifications/routes.py')

    assert "notifications.mark_read" in component
    assert "notifications.mark_all_read" in read(
        'app/templates/components/navigation/_notification_center.html'
    )
    assert 'mark_notification_read(' in routes
    assert 'mark_all_notifications_read(' in routes


def test_activity_page_polls_and_refreshes_topbar_after_read_mutation() -> None:
    page = read('app/templates/notifications/partials/_center_page_content.html')
    routes = read('app/notifications/routes.py')

    assert 'every 15s' in page
    assert 'kaori:notifications-changed from:body' in page
    assert "response.headers['HX-Trigger-After-Swap'] = 'kaori:notifications-changed'" in routes


def test_background_failures_stay_in_activity_center_unless_explicitly_overridden() -> None:
    service = read('app/notifications/service.py')

    assert "event_metadata.get('feedback_delivery')" in service
    assert "if explicit_delivery in {'toast', 'activity_center'}" in service
    assert 'if is_background_event:' in service
    assert "return 'activity_center'" in service
