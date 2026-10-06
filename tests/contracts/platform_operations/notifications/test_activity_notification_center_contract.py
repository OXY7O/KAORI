from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_topbar_uses_one_stable_bell_and_viewport_slider() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert shell.count('aria-label="Open notification deck"') == 1
    assert shell.count('aria-label="Open work inbox"') == 1
    assert shell.count('id="notification-deck"') == 1
    assert 'data-lucide="message-square-text"' in shell
    assert 'work-inbox-badge' in shell
    assert 'data-lucide="bell"' in shell
    assert 'notification-bell-badge' in shell
    assert 'notification-running-indicator' in shell
    assert '<template x-teleport="body">' in shell
    assert 'data-notification-deck-dialog' in shell
    assert 'class="fixed inset-0 z-50"' in shell


def test_deck_and_page_tabs_use_quiet_kaori_surfaces() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    page = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
    framed_tabs = read('app/templates/components/framed_workspace_tabs.html')

    expected_track = 'rounded-xl border border-outline-default bg-surface-hover p-1'

    assert expected_track in shell
    assert 'components/framed_workspace_tabs.html' in page
    assert 'framed_workspace_tabs.render_navigation(' in page
    assert 'border-b border-outline-default bg-surface-hover px-4 pt-4' in framed_tabs
    assert 'bg-surface-card text-kaori-primary' in shell
    assert 'bg-surface-card text-kaori-primary' in framed_tabs
    assert 'role="tablist"' in shell
    assert "aria_label='Notification Center sections'" in page
    assert 'role="tablist"' not in page


def test_deck_auto_refreshes_one_snapshot_every_15_seconds() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    navbar = read('app/templates/components/navigation/navbar.html')
    navbar_js = read('app/static/js/navbar.js')
    layout = read('app/templates/layouts/app.html')
    routes = read('app/platform_operations/notifications/routes.py')

    assert 'data-notification-deck-root' in shell
    assert "url_for('notifications.panel_snapshot')" in shell
    assert 'queueNotificationDeckRefresh()' in navbar
    assert "filename='js/navbar.js'" in layout
    assert 'window.setInterval(() =>' in navbar_js
    assert '}, 15000)' in navbar_js
    assert 'async refreshNotificationDeck()' in navbar_js
    assert 'notificationDeckSnapshotQueued: false' in navbar_js
    assert 'queueNotificationDeckRefresh()' in navbar_js
    assert 'if (this.notificationDeckSnapshotInFlight) {' in navbar_js
    assert 'this.notificationDeckSnapshotQueued = true' in navbar_js
    assert 'const response = await fetch(snapshotUrl' in navbar_js
    assert "Accept: 'application/json'" in navbar_js
    assert "cache: 'no-store'" in navbar_js
    assert "@notifications_bp.get('/panel/snapshot')" in routes
    assert 'return _render_status_snapshot()' in routes
    assert shell.count('hx-trigger="every 15s') == 0


def test_manual_refresh_ui_and_state_are_removed() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    shell = read('app/templates/components/navigation/_notification_center.html')

    shell_only = (
        'aria-label="Refresh activity and notifications now"',
        'data-lucide="refresh-cw"',
        '@click="refreshNotificationDeck(true)"',
        'Refreshing current status',
        'Status refresh failed. Auto refresh will retry.',
    )
    for legacy in shell_only:
        assert legacy not in shell

    navbar_state = (
        'notificationDeckRefreshing',
        'notificationDeckRefreshError',
        'notificationDeckRefreshToken',
        'async refreshNotificationDeck(manual',
    )
    for legacy in navbar_state:
        assert legacy not in navbar


def test_auto_poll_is_bounded_and_never_overlaps() -> None:
    navbar_js = read('app/static/js/navbar.js')

    assert 'notificationDeckSnapshotInFlight: false' in navbar_js
    assert 'notificationDeckSnapshotController: null' in navbar_js
    assert 'notificationDeckSnapshotQueued: false' in navbar_js
    assert 'queueNotificationDeckRefresh()' in navbar_js
    assert 'if (this.notificationDeckSnapshotInFlight) {' in navbar_js
    assert 'this.notificationDeckSnapshotQueued = true' in navbar_js
    assert 'const controller = new AbortController()' in navbar_js
    assert 'window.setTimeout(() => controller.abort(), 5000)' in navbar_js
    assert 'finally {' in navbar_js
    assert 'this.notificationDeckSnapshotInFlight = false' in navbar_js
    assert 'this.notificationDeckSnapshotController?.abort()' in navbar_js


def test_footer_exposes_quiet_auto_refresh_status() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')

    assert 'Auto refresh every 15 seconds' in shell
    assert 'Connection issue · retrying automatically' in shell
    assert 'Updated ${notificationDeckLastChecked}' in shell
    assert 'notificationDeckConnectionIssue' in shell
    assert 'animate-spin' not in shell


def test_snapshot_updates_stable_slots_without_replacing_deck() -> None:
    navbar_js = read('app/static/js/navbar.js')
    routes = read('app/platform_operations/notifications/routes.py')

    for needle in (
        "document.getElementById('notification-deck-active-job-list')",
        "document.getElementById('notification-deck-inbox-content')",
        "document.getElementById('notification-deck-notifications-content')",
        'window.kaoriSafeHtml.replace(activityTarget, payload.activity_html)',
        'window.kaoriSafeHtml.replace(inboxTarget, payload.inbox_html)',
        'window.kaoriSafeHtml.replace(notificationsTarget, payload.notifications_html)',
        'window.htmx?.process(inboxTarget)',
        'window.htmx?.process(notificationsTarget)',
        'window.renderLocalOperationalActivities?.()',
    ):
        assert needle in navbar_js

    assert 'def _count_value(value: object) -> int:' in routes

    for needle in (
        'Blueprint,',
        'jsonify,',
        'def _render_status_snapshot()',
        "'active_count': _count_value(context.get('active_count', 0))",
        "'unread_count': _count_value(context.get('unread_count', 0))",
        "'inbox_unread_count': _count_value(context.get('inbox_unread_count', 0))",
        "'activity_html': render_template(",
        "'inbox_html': render_template(",
        "'notifications_html': render_template(",
        "response.headers['Cache-Control'] = 'no-store, max-age=0'",
    ):
        assert needle in routes


def test_unused_legacy_panel_routes_and_helpers_are_removed() -> None:
    routes = read('app/platform_operations/notifications/routes.py')

    for legacy in (
        "@notifications_bp.get('/panel/refresh')",
        'def panel_refresh()',
        "@notifications_bp.get('/panel/activity')",
        'def panel_activity()',
        "@notifications_bp.get('/panel/notifications')",
        'def panel_notifications()',
        "@notifications_bp.get('/panel')",
        'def _render_activity_panel(',
    ):
        assert legacy not in routes


def test_activity_panel_uses_stable_local_and_server_slots() -> None:
    activity = read('app/templates/platform_operations/notifications/partials/_notification_deck_activity.html')
    jobs = read('app/templates/platform_operations/notifications/partials/_notification_deck_activity_jobs.html')

    assert 'data-activity-surface' in activity
    assert 'data-local-activity-list' in activity
    assert 'id="notification-deck-active-job-list"' in activity
    assert 'data-running-empty' in activity
    assert 'data-activity-count-label' in activity
    assert 'data-server-activity-item' in jobs
    assert 'data-activity-dynamic-source' not in activity


def test_queued_jobs_do_not_look_like_a_never_ending_refresh() -> None:
    component = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    progress = read('app/templates/components/progress_bar.html')
    presentation = read('app/common/job_execution_presentation.py')

    assert 'progress_bar.job_progress(' in component
    assert "job.progress_mode == 'queued'" in progress
    assert 'w-1/4 rounded-full bg-kaori-primary/55' in progress
    assert "if job.status == 'queued':\n        return 'Waiting'" in presentation
    assert 'job.queue_health.show_warning' in component


def test_activity_reconciliation_counts_stable_items_without_dynamic_pollers() -> None:
    runtime = read('app/static/js/application_shell.js')
    layout = read('app/templates/layouts/app.html')
    page = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

    assert "surface.querySelectorAll('[data-server-activity-item]').length" in runtime
    assert "document.getElementById('notification-deck-active-count')" in runtime
    assert "emptyState.classList.toggle('hidden', totalCount > 0)" in runtime
    assert 'data-activity-dynamic-source' not in runtime
    assert "filename='js/application_shell.js'" in layout
    assert 'data-server-activity-item' in page


def test_notification_mutations_target_only_stable_notification_content() -> None:
    component = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    notifications = read(
        'app/templates/platform_operations/notifications/partials/_notification_deck_notifications.html'
    )
    inbox = read('app/templates/platform_operations/notifications/partials/_notification_deck_inbox.html')
    routes = read('app/platform_operations/notifications/routes.py')

    assert 'hx-swap="{{ swap }}"' in component
    assert "target='#notification-deck-notifications-content'" in notifications
    assert 'hx-target="#notification-deck-notifications-content"' in notifications
    assert 'hx-swap="innerHTML"' in notifications
    assert "target='#notification-deck-inbox-content'" in inbox
    assert 'hx-target="#notification-deck-inbox-content"' in inbox
    assert "scope='inbox'" in inbox
    assert "scope='notifications'" in notifications
    assert 'return _render_inbox_panel()' in routes
    assert 'return _render_notifications_panel()' in routes


def test_notification_item_accepts_explicit_panel_view_for_snapshot_fragments() -> None:
    component = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    inbox = read('app/templates/platform_operations/notifications/partials/_notification_deck_inbox.html')
    notifications = read(
        'app/templates/platform_operations/notifications/partials/_notification_deck_notifications.html'
    )

    assert 'per_page=none, view=none' in component
    assert "mutation_view = view or request.args.get('view', 'notifications')" in component
    assert 'view=mutation_view' in component
    assert "view='inbox'" in inbox
    assert "view='notifications'" in notifications


def test_oob_badges_remain_available_for_notification_mutations() -> None:
    oob = read('app/templates/platform_operations/notifications/partials/_notification_deck_oob.html')

    assert oob.count('hx-swap-oob="outerHTML"') == 6
    assert 'work-inbox-badge' in oob
    assert 'notification-deck-inbox-count' in oob
    assert 'notification-bell-badge' in oob
    assert 'notification-running-indicator' in oob
    assert 'notification-deck-active-count' in oob
    assert 'notification-deck-unread-count' in oob


def test_full_notifications_page_keeps_15_second_auto_refresh() -> None:
    page = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

    assert 'hx-trigger="kaori:notifications-changed from:body, every 15s"' in page
    assert 'hx-target="this"' in page
    assert 'hx-swap="outerHTML"' in page


def test_legacy_self_replacing_deck_fragments_are_removed() -> None:
    assert not (
        ROOT / 'app/templates/platform_operations/notifications/partials/_notification_deck_content.html'
    ).exists()
    assert not (
        ROOT / 'app/templates/platform_operations/notifications/partials/_notification_deck_refresh.html'
    ).exists()


def test_refresh_standard_is_documented() -> None:
    readme = read('app/platform_operations/notifications/README.md')

    assert '/notifications/panel/snapshot' in readme
    assert 'The deck has no manual refresh button, spinner, or manual-refresh state.' in readme
    assert 'allows only one request at a time' in readme


def test_inventory_quick_action_relies_on_canonical_auto_refresh() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    quick_sync = read('app/kubernetes/cluster/quick_sync.py')
    queries = read('app/platform_operations/notifications/queries.py')

    assert 'hx-swap="none"' in navbar
    assert 'hx-target="#quick-sync-feedback"' not in navbar
    assert 'quick-sync-feedback' not in navbar
    assert 'data-operational-progress-title="Inventory Sync"' not in navbar
    assert 'data-operational-progress-message="Registering the fleet inventory job' not in navbar
    assert '@click="quickOpen = false"' in navbar
    assert (
        'notificationDeckOpen = true'
        not in navbar[
            navbar.index('id="quick-sync-form"') : navbar.index('</form>', navbar.index('id="quick-sync-form"'))
        ]
    )

    assert 'def _htmx_dispatch_response(' in quick_sync
    assert "response.headers['HX-Trigger']" not in quick_sync
    assert 'HX-Trigger-After-Swap' not in quick_sync
    assert "'source': 'inventory_quick_action'" not in quick_sync
    assert 'def _activity_center_response(' not in quick_sync
    assert 'def _trigger_notification_snapshot(' not in quick_sync

    # Success is represented only by the canonical JobExecution row.
    success_block = quick_sync[
        quick_sync.index('outcome = dispatch_registered_job(') : quick_sync.index(
            '    except (', quick_sync.index('outcome = dispatch_registered_job(')
        )
    ]
    assert "title='Inventory Sync Queued'" not in success_block
    assert "'job_execution_id': job.id" not in success_block
    assert "event_type='kubernetes_inventory_sync'" in quick_sync  # blocked/error notifications remain

    assert 'JobExecution.requested_by_user_id == user_id' in queries
    assert 'JobExecutionSubscriber.user_id == user_id' in queries
