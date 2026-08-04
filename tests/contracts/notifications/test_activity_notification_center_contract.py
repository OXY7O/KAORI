from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_topbar_uses_one_stable_bell_for_notification_deck() -> None:
    trigger = read('app/templates/components/navigation/_notification_center.html')

    assert trigger.count('aria-label="Open notification deck"') == 1
    assert 'data-lucide="bell"' in trigger
    assert 'data-lucide="activity"' not in trigger
    assert 'notification-bell-badge' in trigger
    assert 'notification-running-indicator' in trigger
    assert 'hx-trigger=' not in trigger


def test_slider_deck_is_teleported_outside_the_sticky_navbar() -> None:
    trigger = read('app/templates/components/navigation/_notification_center.html')

    assert '<template x-teleport="body">' in trigger
    assert 'class="fixed inset-0 z-50"' in trigger
    assert 'bg-surface-overlay/70' in trigger
    assert 'h-full w-full max-w-md' in trigger
    assert 'max-w-[28rem]' not in trigger
    assert 'bg-surface-overlay/80' not in trigger


def test_slider_deck_has_activity_and_notifications_tabs() -> None:
    deck = read('app/templates/notifications/partials/_notification_deck_content.html')

    assert "notificationDeckTab = 'activity'" in deck
    assert "notificationDeckTab = 'notifications'" in deck
    assert 'data-local-activity-list' in deck
    assert "target='#notification-deck-content'" in deck
    assert 'Live refresh every 15 seconds' in deck


def test_polling_replaces_only_deck_content_without_load_loop() -> None:
    trigger = read('app/templates/components/navigation/_notification_center.html')
    deck = read('app/templates/notifications/partials/_notification_deck_content.html')
    routes = read('app/notifications/routes.py')

    assert 'hx-target="#notification-deck-content"' in trigger
    assert 'hx-trigger="every 15s, kaori:notifications-changed from:body"' in deck
    assert 'load, every 15s' not in deck
    assert "'notifications/partials/_notification_deck_content.html'" in routes
    assert 'emit_oob=emit_oob' in routes


def test_deck_and_full_page_share_one_activity_center_context() -> None:
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


def test_background_progress_uses_deck_instead_of_progress_toasts() -> None:
    layout = read('app/templates/layouts/app.html')
    feedback = read('app/notifications/service.py')
    toast = read('app/templates/components/navigation/_quick_sync_result.html')

    assert 'showOperationalProgressToast' not in layout
    assert 'startOperationalActivity' in layout
    assert 'notification-running-indicator' in layout
    assert "return 'activity_center'" in feedback
    assert "delivery|default('toast') == 'activity_center'" in toast


def test_notification_page_matches_two_deck_sections() -> None:
    page = read('app/templates/notifications/partials/_center_page_content.html')
    routes = read('app/notifications/routes.py')

    assert "view='activity'" in page
    assert "view='notifications'" in page
    assert "frozenset({'activity', 'notifications'})" in routes
    assert 'every 15s' in page
    assert 'kaori:notifications-changed from:body' in page


def test_explicit_read_semantics_refresh_deck_badges() -> None:
    component = read('app/templates/notifications/components/_activity_center_items.html')
    deck = read('app/templates/notifications/partials/_notification_deck_content.html')
    routes = read('app/notifications/routes.py')

    assert 'notifications.mark_read' in component
    assert 'notifications.mark_all_read' in deck
    assert 'hx-swap-oob="outerHTML"' in deck
    assert 'mark_notification_read(' in routes
    assert 'mark_all_notifications_read(' in routes


def test_background_failures_stay_in_activity_center_unless_overridden() -> None:
    service = read('app/notifications/service.py')

    assert "event_metadata.get('feedback_delivery')" in service
    assert "if explicit_delivery in {'toast', 'activity_center'}" in service
    assert 'if is_background_event:' in service
    assert "return 'activity_center'" in service
