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


def test_auto_refresh_uses_one_read_only_snapshot_every_15_seconds() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    navbar = read('app/templates/components/navigation/navbar.html')
    routes = read('app/notifications/routes.py')

    assert 'id="notification-deck-refresh-coordinator"' in shell
    assert "url_for('notifications.panel_refresh')" in shell
    assert 'window.setInterval(() =>' in navbar
    assert '}, 15000)' in navbar
    assert 'const response = await fetch(refreshUrl' in navbar
    assert "Accept: 'application/json'" in navbar
    assert "cache: 'no-store'" in navbar
    assert "@notifications_bp.get('/panel/refresh')" in routes
    assert 'return _render_refresh_snapshot()' in routes

    assert 'window.htmx.ajax' not in navbar
    assert 'await this.notificationDeckRefreshInFlight' not in navbar
    assert shell.count('hx-trigger="every 15s') == 0


def test_manual_refresh_aborts_older_poll_and_always_stops() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert 'async refreshNotificationDeck(manual = true)' in navbar
    assert 'notificationDeckRefreshController: null' in navbar
    assert 'notificationDeckRefreshToken: 0' in navbar
    assert 'if (manual && this.notificationDeckRefreshController)' in navbar
    assert 'this.notificationDeckRefreshController.abort()' in navbar
    assert 'const controller = new AbortController()' in navbar
    assert 'window.setTimeout(() => controller.abort(), 5000)' in navbar
    assert 'finally {' in navbar
    assert 'this.notificationDeckRefreshing = false' in navbar

    assert '@click="refreshNotificationDeck(true)"' in shell
    assert ':disabled="notificationDeckRefreshing"' in shell
    assert "notificationDeckRefreshing ? 'animate-spin' : ''" in shell
    assert 'Refreshing current status' in shell
    assert 'Status refresh failed. Auto refresh will retry.' in shell


def test_snapshot_updates_stable_slots_without_replacing_deck() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    routes = read('app/notifications/routes.py')

    for needle in (
        "document.getElementById('notification-deck-active-job-list')",
        "document.getElementById('notification-deck-notifications-content')",
        'activityTarget.innerHTML = payload.activity_html',
        'notificationsTarget.innerHTML = payload.notifications_html',
        'window.htmx?.process(notificationsTarget)',
        'window.renderLocalOperationalActivities?.()',
    ):
        assert needle in navbar

    for needle in (
        'from flask import Blueprint, jsonify,',
        'def _render_refresh_snapshot()',
        "'active_count': int(context.get('active_count', 0))",
        "'unread_count': int(context.get('unread_count', 0))",
        "'activity_html': render_template(",
        "'notifications_html': render_template(",
        "response.headers['Cache-Control'] = 'no-store, max-age=0'",
    ):
        assert needle in routes

    assert not (
        ROOT / 'app/templates/notifications/partials/_notification_deck_refresh.html'
    ).exists()


def test_refresh_button_is_a_colored_icon_block() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert 'border border-kaori-primary bg-kaori-primary text-white' in shell
    assert 'hover:bg-kaori-primary-hover' in shell
    assert 'aria-label="Refresh activity and notifications now"' in shell
    assert 'notificationDeckLastChecked' in shell
    assert 'Last checked ${notificationDeckLastChecked}' in shell


def test_activity_panel_uses_stable_local_and_server_slots() -> None:
    activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
    jobs = read('app/templates/notifications/partials/_notification_deck_activity_jobs.html')

    assert 'data-activity-surface' in activity
    assert 'data-local-activity-list' in activity
    assert 'id="notification-deck-active-job-list"' in activity
    assert 'data-running-empty' in activity
    assert 'data-activity-count-label' in activity
    assert 'data-server-activity-item' in jobs

    assert 'data-activity-dynamic-source' not in activity
    assert 'visible_jobs' not in activity
    assert 'inventory_sync_all' not in activity
    assert 'inventory_sync_cluster' not in activity


def test_queued_jobs_do_not_look_like_a_never_ending_refresh() -> None:
    component = read('app/templates/notifications/components/_activity_center_items.html')
    presentation = read('app/jobs/presentation.py')

    assert "elif job.progress_mode == 'queued'" in component
    assert 'w-1/3 rounded-full bg-kaori-primary/60' in component
    assert "if job.status == 'queued':\n        return 'Waiting'" in presentation


def test_activity_reconciliation_counts_stable_items_without_dynamic_pollers() -> None:
    layout = read('app/templates/layouts/app.html')
    page = read('app/templates/notifications/partials/_center_page_content.html')

    assert "surface.querySelectorAll('[data-server-activity-item]').length" in layout
    assert "document.getElementById('notification-deck-active-count')" in layout
    assert "emptyState.classList.toggle('hidden', totalCount > 0)" in layout
    assert 'data-activity-dynamic-source' not in layout
    assert 'activityServerCount' not in layout
    assert 'data-server-activity-item' in page


def test_notification_mutations_target_only_stable_notification_content() -> None:
    component = read('app/templates/notifications/components/_activity_center_items.html')
    notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')
    routes = read('app/notifications/routes.py')

    assert 'hx-swap="{{ swap }}"' in component
    assert "target='#notification-deck-notifications-content'" in notifications
    assert 'hx-target="#notification-deck-notifications-content"' in notifications
    assert 'hx-swap="innerHTML"' in notifications
    assert 'return _render_notifications_panel()' in routes


def test_oob_badges_remain_available_for_notification_mutations() -> None:
    oob = read('app/templates/notifications/partials/_notification_deck_oob.html')

    assert oob.count('hx-swap-oob="outerHTML"') == 4
    assert 'notification-bell-badge' in oob
    assert 'notification-running-indicator' in oob
    assert 'notification-deck-active-count' in oob
    assert 'notification-deck-unread-count' in oob


def test_panel_routes_keep_no_store_policy_and_compatibility_endpoints() -> None:
    routes = read('app/notifications/routes.py')

    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "@notifications_bp.get('/panel/refresh')" in routes
    assert "@notifications_bp.get('/panel/activity')" in routes
    assert "@notifications_bp.get('/panel/notifications')" in routes
    assert "'_notification_deck_content.html'" not in routes


def test_legacy_stuck_refresh_contract_is_removed() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    navbar = read('app/templates/components/navigation/navbar.html')

    for legacy in (
        'kaori:notification-deck-refresh-complete',
        'notificationDeckRefreshPending',
        'notificationDeckRefreshInFlight',
        'await Promise.race([request, timeout])',
        'window.htmx.ajax',
        'await this.notificationDeckRefreshInFlight',
        "window.htmx.trigger(document.body, 'kaori:notification-deck-refresh')",
    ):
        assert legacy not in shell
        assert legacy not in navbar


def test_background_progress_stays_out_of_stacked_toasts() -> None:
    layout = read('app/templates/layouts/app.html')
    feedback = read('app/notifications/service.py')

    assert 'showOperationalProgressToast' not in layout
    assert 'startOperationalActivity' in layout
    assert 'notification-running-indicator' in layout
    assert "return 'activity_center'" in feedback


def test_legacy_self_replacing_deck_fragments_are_removed() -> None:
    assert not (
        ROOT / 'app/templates/notifications/partials/_notification_deck_content.html'
    ).exists()
    assert not (
        ROOT / 'app/templates/notifications/partials/_notification_deck_refresh.html'
    ).exists()
