#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise SystemExit(f'Missing Notification Deck file: {relative}')
    return path.read_text(encoding='utf-8')


required_files = (
    'app/templates/components/navigation/_notification_center.html',
    'app/templates/notifications/partials/_notification_deck_activity.html',
    'app/templates/notifications/partials/_notification_deck_activity_jobs.html',
    'app/templates/notifications/partials/_notification_deck_notifications.html',
    'app/templates/notifications/partials/_notification_deck_oob.html',
    'app/templates/notifications/components/_activity_center_items.html',
    'app/templates/components/progress_bar.html',
    'app/notifications/routes.py',
    'app/notifications/queries.py',
    'app/notifications/service.py',
    'app/common/job_execution_presentation.py',
    'app/jobs/presentation.py',
    'app/templates/notifications/index.html',
    'app/templates/notifications/partials/_center_page_content.html',
    'app/templates/layouts/app.html',
    'app/templates/components/navigation/navbar.html',
    'app/static/js/navbar.js',
)
for relative in required_files:
    read(relative)

shell = read('app/templates/components/navigation/_notification_center.html')
navbar = read('app/templates/components/navigation/navbar.html')
navbar_js = read('app/static/js/navbar.js')
activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
activity_jobs = read('app/templates/notifications/partials/_notification_deck_activity_jobs.html')
notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')
oob = read('app/templates/notifications/partials/_notification_deck_oob.html')
component = read('app/templates/notifications/components/_activity_center_items.html')
progress_component = read('app/templates/components/progress_bar.html')
routes = read('app/notifications/routes.py')
presentation = read('app/common/job_execution_presentation.py')
layout = read('app/templates/layouts/app.html')
page_tabs = read('app/templates/notifications/partials/_center_page_content.html')
readme = read('app/notifications/README.md')
quick_sync = read('app/cluster/quick_sync.py')
queries = read('app/notifications/queries.py')

if shell.count('aria-label="Open notification deck"') != 1:
    raise SystemExit('Top bar must expose exactly one Notification Deck trigger.')
for needle in (
    'x-teleport="body"',
    'data-notification-deck-dialog',
    'id="notification-deck-activity"',
    'id="notification-deck-notifications"',
    'data-notification-deck-root',
    "url_for('notifications.panel_snapshot')",
    'notification-bell-badge',
    'notification-running-indicator',
):
    if needle not in shell:
        raise SystemExit(f'Notification shell is missing stable-deck contract: {needle}')

for needle in (
    'role="tablist"',
    'rounded-xl border border-outline-default bg-surface-hover p-1',
    "notificationDeckTab === 'activity'",
    'bg-surface-card text-kaori-primary shadow-sm dark:text-kaori-accent',
    ":class=\"notificationDeckTab === 'activity' ? 'block' : 'hidden'\"",
    'Auto refresh every 15 seconds',
    'Connection issue · retrying automatically',
    'Updated ${notificationDeckLastChecked}',
):
    if needle not in shell:
        raise SystemExit(f'Notification Deck is missing automatic refresh/tab contract: {needle}')

for forbidden in (
    'aria-label="Refresh activity and notifications now"',
    'data-lucide="refresh-cw"',
    '@click="refreshNotificationDeck(true)"',
    'notificationDeckRefreshing',
    'notificationDeckRefreshError',
    'Refreshing current status',
    'Status refresh failed. Auto refresh will retry.',
):
    if forbidden in shell:
        raise SystemExit(f'Manual refresh UI or state remains in Notification Deck: {forbidden}')

for needle in (
    'notificationDeckSnapshotInFlight: false',
    'notificationDeckSnapshotController: null',
    'notificationDeckConnectionIssue: false',
    'notificationDeckLastChecked: null',
    'window.setInterval(() =>',
    '}, 15000)',
    'async refreshNotificationDeck()',
    'notificationDeckSnapshotQueued: false',
    'queueNotificationDeckRefresh()',
    'if (this.notificationDeckSnapshotInFlight) {',
    'this.notificationDeckSnapshotQueued = true',
    'const controller = new AbortController()',
    'window.setTimeout(() => controller.abort(), 5000)',
    'const response = await fetch(snapshotUrl',
    "Accept: 'application/json'",
    "cache: 'no-store'",
    'const payload = await response.json()',
    'this.applyNotificationDeckSnapshot(payload)',
    'this.notificationDeckSnapshotInFlight = false',
    'window.queueMicrotask(() => this.refreshNotificationDeck())',
):
    if needle not in navbar_js:
        raise SystemExit(f'Navbar runtime is missing bounded automatic snapshot lifecycle: {needle}')

if '@kaori:notifications-changed.window="if ($event.detail?.tab' not in navbar:
    raise SystemExit('Navbar template is missing the Notification Deck change-event bridge.')

for forbidden in (
    "response.headers['HX-Trigger']",
    "response.headers['HX-Trigger-After-Swap']",
    "'source': 'inventory_quick_action'",
    'def _activity_center_response(',
    'def _trigger_notification_snapshot(',
    'trigger_notification_refresh=True',
):
    if forbidden in quick_sync:
        raise SystemExit(f'Inventory Quick Action still forces Notification Deck refresh/open behavior: {forbidden}')

for needle in (
    'def _htmx_dispatch_response(',
    "event_type='kubernetes_inventory_sync'",
):
    if needle not in quick_sync:
        raise SystemExit(f'Inventory Quick Action dispatch contract is missing: {needle}')

for forbidden in (
    'data-operational-progress-title="Inventory Sync"',
    'data-operational-progress-message="Registering the fleet inventory job',
):
    if forbidden in navbar:
        raise SystemExit(f'Inventory Quick Action still creates foreground Activity state: {forbidden}')

quick_form_start = navbar.find('id="quick-sync-form"')
quick_form_end = navbar.find('</form>', quick_form_start)
quick_form = navbar[quick_form_start:quick_form_end] if quick_form_start >= 0 and quick_form_end >= 0 else ''
if not quick_form:
    raise SystemExit('Inventory Quick Action form is missing.')
if '@click="quickOpen = false"' not in quick_form:
    raise SystemExit('Inventory Quick Action must close only the Quick Actions menu.')
if 'notificationDeckOpen = true' in quick_form or "notificationDeckTab = 'activity'" in quick_form:
    raise SystemExit('Inventory Quick Action still opens or changes the Notification Deck.')
if 'hx-swap="none"' not in quick_form:
    raise SystemExit('Inventory Quick Action must remain an eventless dispatch surface.')

if 'quick-sync-feedback' in navbar:
    raise SystemExit('Inventory Quick Action still targets the removed #quick-sync-feedback element.')

for needle in (
    'JobExecution.requested_by_user_id == user_id',
    'JobExecutionSubscriber.user_id == user_id',
):
    if needle not in queries:
        raise SystemExit(f'Activity visibility does not include the Quick Action requester/subscriber: {needle}')

for forbidden in (
    'notificationDeckRefreshInFlight',
    'notificationDeckRefreshToken',
    'notificationDeckRefreshing',
    'notificationDeckRefreshError',
    'async refreshNotificationDeck(manual',
    'window.htmx.ajax',
    'await Promise.race([request, timeout])',
    "window.htmx.trigger(document.body, 'kaori:notification-deck-refresh')",
):
    if forbidden in navbar_js:
        raise SystemExit(f'Legacy/manual refresh state remains in navbar runtime: {forbidden}')

for needle in (
    "document.getElementById('notification-deck-active-job-list')",
    "document.getElementById('notification-deck-notifications-content')",
    'activityTarget.innerHTML = payload.activity_html',
    'notificationsTarget.innerHTML = payload.notifications_html',
    'window.htmx?.process(notificationsTarget)',
    'window.renderLocalOperationalActivities?.()',
):
    if needle not in navbar_js:
        raise SystemExit(f'Snapshot application is missing stable-slot update: {needle}')

for needle in (
    'from flask import (',
    'Blueprint,',
    'jsonify,',
    'def _render_status_snapshot()',
    'never wait for queued workers to finish',
    "'active_count': _count_value(context.get('active_count', 0))",
    "'unread_count': _count_value(context.get('unread_count', 0))",
    "'activity_html': render_template(",
    "'notifications_html': render_template(",
    "@notifications_bp.get('/panel/snapshot')",
    'return _render_status_snapshot()',
    "response.headers['Cache-Control'] = 'no-store, max-age=0'",
):
    if needle not in routes:
        raise SystemExit(f'Notification routes are missing automatic snapshot contract: {needle}')

for forbidden in (
    "@notifications_bp.get('/panel/refresh')",
    'def panel_refresh()',
    "@notifications_bp.get('/panel/activity')",
    'def panel_activity()',
    "@notifications_bp.get('/panel/notifications')",
    'def panel_notifications()',
    "@notifications_bp.get('/panel')",
    'def _render_activity_panel(',
):
    if forbidden in routes:
        raise SystemExit(f'Unused legacy panel route/helper remains: {forbidden}')

for needle in (
    'data-local-activity-list',
    'id="notification-deck-active-job-list"',
    'data-running-empty',
    'data-activity-surface',
    'data-activity-count-label',
):
    if needle not in activity:
        raise SystemExit(f'Activity panel is missing stable-slot contract: {needle}')
if 'data-server-activity-item' not in activity_jobs:
    raise SystemExit('Activity job fragment does not expose stable server activity items.')

for source, required in (
    (activity, ('Processes in Progress', 'Active', 'No Process Is Running')),
    (notifications, ('Recent Notifications', 'Mark All Read', 'Needs Attention', 'Need Attention')),
    (component, ('View Details', 'Mark Read')),
    (shell, ('View All',)),
):
    for needle in required:
        if needle not in source:
            raise SystemExit(f'Notification Deck Title Case contract missing: {needle}')

for source, forbidden in (
    (activity, ('Processes in progress', 'No process is running', '&nbsp;active')),
    (notifications, ('Recent notifications', 'Mark all read', ' need attention')),
    (component, ('View details', 'Mark read')),
    (shell, ('View all <i',)),
):
    for needle in forbidden:
        if needle in source:
            raise SystemExit(f'Notification Deck legacy casing remains: {needle}')

if "if job.progress_mode == 'queued'" not in progress_component:
    raise SystemExit('Queued jobs must use a static progress marker.')
if 'w-1/4 rounded-full bg-kaori-primary/55' not in progress_component:
    raise SystemExit('Queued job marker is missing the non-animated KAORI style.')
if "if job.status == 'queued':\n        return 'Waiting'" not in presentation:
    raise SystemExit('Queued duration must read Waiting instead of In progress.')

for needle in (
    "target='#notification-deck-notifications-content'",
    'hx-target="#notification-deck-notifications-content"',
    'hx-swap="innerHTML"',
):
    if needle not in notifications:
        raise SystemExit(f'Notifications panel is missing stable content target: {needle}')

for needle in (
    "surface.querySelectorAll('[data-server-activity-item]').length",
    "document.getElementById('notification-deck-active-count')",
    "emptyState.classList.toggle('hidden', totalCount > 0)",
):
    if needle not in layout:
        raise SystemExit(f'Activity surface reconciliation is missing: {needle}')

for needle in (
    'components/framed_workspace_tabs.html',
    'framed_workspace_tabs.render_navigation(',
    "aria_label='Notification Center sections'",
    "selected_view == 'activity'",
    "selected_view == 'notifications'",
    'data-server-activity-item',
    'every 15s',
):
    if needle not in page_tabs:
        raise SystemExit(f'Notifications page is not aligned with deck tabs: {needle}')

for needle in (
    'The deck has no manual refresh button, spinner, or manual-refresh state.',
    '/notifications/panel/snapshot',
    'allows only one request at a time',
):
    if needle not in readme:
        raise SystemExit(f'Notification refresh standard is not documented: {needle}')

if oob.count('hx-swap-oob="outerHTML"') != 4:
    raise SystemExit('OOB badge fragment must remain available for mutation responses.')
if 'showOperationalProgressToast' in layout:
    raise SystemExit('Legacy operational progress toast remains active in app layout.')
for legacy_path in (
    'app/templates/notifications/partials/_notification_deck_content.html',
    'app/templates/notifications/partials/_notification_deck_refresh.html',
):
    if (ROOT / legacy_path).exists():
        raise SystemExit(f'Legacy self-replacing Notification Deck fragment remains: {legacy_path}')

print(
    'KAORI Notification Deck audit passed: Activity and Notifications auto-refresh from '
    'one bounded snapshot every 15 seconds, opening the deck requests current status, '
    'manual refresh code is absent, Quick Action inventory sync dispatches without opening '
    'or forcing the deck, canonical jobs appear through the normal snapshot cycle, queued '
    'workers never block polling, and stable content slots prevent flicker.'
)
