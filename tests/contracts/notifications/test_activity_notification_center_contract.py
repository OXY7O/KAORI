from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_topbar_uses_one_stable_bell_and_viewport_slider() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert shell.count('aria-label="Open notification deck"') == 1
    assert 'data-lucide="bell"' in shell
    assert 'notification-bell-badge' in shell
    assert 'notification-running-indicator' in shell
    assert '<template x-teleport="body">' in shell
    assert 'data-notification-deck-dialog' in shell
    assert 'class="fixed inset-0 z-50"' in shell


def test_polling_never_replaces_alpine_slider_shell() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert 'id="notification-deck-activity"' in shell
    assert 'id="notification-deck-notifications"' in shell
    assert shell.count('hx-swap="innerHTML"') == 2
    assert 'hx-swap="outerHTML"' not in shell
    assert "url_for('notifications.panel_activity')" in shell
    assert "url_for('notifications.panel_notifications')" in shell
    assert "url_for('notifications.panel')" not in shell


def test_deck_uses_independent_stable_activity_and_notification_fragments() -> None:
    activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
    notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')

    assert 'data-local-activity-list' in activity
    assert 'data-running-empty' in activity
    assert 'data-notification-deck-activity-body' in activity
    assert 'data-notification-deck-notifications-body' in notifications
    assert "target='#notification-deck-notifications'" in notifications
    assert "swap='innerHTML'" in notifications
    assert 'hx-target="#notification-deck-notifications"' in notifications
    assert 'hx-swap="innerHTML"' in notifications


def test_legacy_self_replacing_deck_fragment_is_removed() -> None:
    assert not (
        ROOT / 'app/templates/notifications/partials/_notification_deck_content.html'
    ).exists()


def test_panel_routes_return_inner_fragments_with_no_store_policy() -> None:
    routes = read('app/notifications/routes.py')

    assert "@notifications_bp.get('/panel/activity')" in routes
    assert "@notifications_bp.get('/panel/notifications')" in routes
    assert "'notifications/partials/_notification_deck_activity.html'" in routes
    assert "'notifications/partials/_notification_deck_notifications.html'" in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "'_notification_deck_content.html'" not in routes


def test_read_actions_refresh_only_stable_notifications_panel() -> None:
    component = read('app/templates/notifications/components/_activity_center_items.html')
    notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')
    routes = read('app/notifications/routes.py')

    assert "swap='outerHTML'" in component
    assert 'hx-swap="{{ swap }}"' in component
    assert "swap='innerHTML'" in notifications
    assert 'return _render_notifications_panel()' in routes
    assert 'mark_notification_read(' in routes
    assert 'mark_all_notifications_read(' in routes


def test_oob_badges_stay_synchronized_without_replacing_shell() -> None:
    oob = read('app/templates/notifications/partials/_notification_deck_oob.html')

    assert oob.count('hx-swap-oob="outerHTML"') == 4
    assert 'notification-bell-badge' in oob
    assert 'notification-running-indicator' in oob
    assert 'notification-deck-active-count' in oob
    assert 'notification-deck-unread-count' in oob


def test_manual_and_automatic_refresh_target_stable_panels() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert "kaori:notification-deck-refresh from:body" in shell
    navbar = read('app/templates/components/navigation/navbar.html')
    assert "window.htmx.trigger(document.body, 'kaori:notification-deck-refresh')" in navbar
    assert shell.count('every 15s') == 2
    assert shell.count('hx-sync="this:replace"') == 2


def test_deck_and_full_page_share_canonical_context() -> None:
    routes = read('app/notifications/routes.py')
    service = read('app/notifications/service.py')
    query = read('app/notifications/queries.py')
    page = read('app/templates/notifications/index.html')

    assert 'get_activity_center_context' in service
    assert 'get_navigation_notification_context' in routes
    assert 'JobExecution.subscribers.any' in query
    assert 'JobExecution.requested_by_user_id == user_id' in query
    assert 'activity_center.active_count' in page
    assert 'activity_center.unread_count' in page


def test_background_progress_stays_out_of_stacked_toasts() -> None:
    layout = read('app/templates/layouts/app.html')
    feedback = read('app/notifications/service.py')

    assert 'showOperationalProgressToast' not in layout
    assert 'startOperationalActivity' in layout
    assert 'notification-running-indicator' in layout
    assert "return 'activity_center'" in feedback


def test_tabs_match_report_type_guide_segmented_control() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    page = read('app/templates/notifications/partials/_center_page_content.html')

    expected_track = 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1'
    expected_active = "bg-surface-card text-kaori-primary shadow-sm"

    assert expected_track in shell
    assert expected_track in page
    assert expected_active in shell
    assert expected_active in page
    assert 'role="tablist"' in shell
    assert 'aria-label="Notification center sections"' in page


def test_activity_tab_always_has_visible_content_contract() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
    layout = read('app/templates/layouts/app.html')

    assert ":class=\"notificationDeckTab === 'activity' ? 'block' : 'hidden'\"" in shell
    assert 'data-activity-surface' in activity
    assert 'data-activity-server-count' in activity
    assert 'data-activity-dynamic-source' in activity
    assert 'visible_jobs' in activity
    assert 'data-running-empty' in activity
    assert "document.querySelectorAll('[data-activity-surface]')" in layout
    assert "surface.querySelectorAll('[data-activity-dynamic-source]')" in layout


def test_manual_refresh_exposes_loading_until_both_panels_finish() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert 'notificationDeckRefreshing: false' in navbar
    assert 'notificationDeckRefreshPending: 0' in navbar
    assert 'this.notificationDeckRefreshPending = 2' in navbar
    assert 'finishNotificationDeckRefresh()' in navbar
    assert '@kaori:notification-deck-refresh-complete.window' in navbar
    assert '@click="refreshNotificationDeck()"' in shell
    assert ':disabled="notificationDeckRefreshing"' in shell
    assert "notificationDeckRefreshing ? 'animate-spin' : ''" in shell
    assert shell.count('kaori:notification-deck-refresh-complete') == 2
    assert 'Refreshing activity and notifications' in shell
