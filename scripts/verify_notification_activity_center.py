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
    'app/notifications/routes.py',
    'app/notifications/queries.py',
    'app/notifications/service.py',
    'app/jobs/presentation.py',
    'app/templates/notifications/index.html',
    'app/templates/notifications/partials/_center_page_content.html',
    'app/templates/layouts/app.html',
    'app/templates/components/navigation/navbar.html',
)
for relative in required_files:
    read(relative)

shell = read('app/templates/components/navigation/_notification_center.html')
navbar = read('app/templates/components/navigation/navbar.html')
activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
activity_jobs = read('app/templates/notifications/partials/_notification_deck_activity_jobs.html')
notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')
oob = read('app/templates/notifications/partials/_notification_deck_oob.html')
component = read('app/templates/notifications/components/_activity_center_items.html')
routes = read('app/notifications/routes.py')
presentation = read('app/jobs/presentation.py')
layout = read('app/templates/layouts/app.html')
page_tabs = read('app/templates/notifications/partials/_center_page_content.html')

if shell.count('aria-label="Open notification deck"') != 1:
    raise SystemExit('Top bar must expose exactly one Notification Deck trigger.')
for needle in (
    'x-teleport="body"',
    'data-notification-deck-dialog',
    'id="notification-deck-activity"',
    'id="notification-deck-notifications"',
    'id="notification-deck-refresh-coordinator"',
    "url_for('notifications.panel_refresh')",
    'notification-bell-badge',
    'notification-running-indicator',
):
    if needle not in shell:
        raise SystemExit(f'Notification shell is missing stable-deck contract: {needle}')

for needle in (
    'role="tablist"',
    'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1',
    "notificationDeckTab === 'activity' ? 'bg-surface-card text-kaori-primary shadow-sm'",
    ':class="notificationDeckTab === \'activity\' ? \'block\' : \'hidden\'"',
    '@click="refreshNotificationDeck(true)"',
    ':disabled="notificationDeckRefreshing"',
    "notificationDeckRefreshing ? 'animate-spin' : ''",
    'border border-kaori-primary bg-kaori-primary text-white',
    'Auto refresh every 15 seconds',
    'Refreshing current status',
    'Status refresh failed. Auto refresh will retry.',
    'Last checked ${notificationDeckLastChecked}',
):
    if needle not in shell:
        raise SystemExit(f'Notification Deck is missing professional refresh/tab contract: {needle}')

for needle in (
    'notificationDeckRefreshing: false',
    'notificationDeckRefreshError: false',
    'notificationDeckRefreshController: null',
    'notificationDeckRefreshToken: 0',
    'notificationDeckLastChecked: null',
    'window.setInterval(() =>',
    '}, 15000)',
    'async refreshNotificationDeck(manual = true)',
    'const controller = new AbortController()',
    'window.setTimeout(() => controller.abort(), 5000)',
    'const response = await fetch(refreshUrl',
    "Accept: 'application/json'",
    "cache: 'no-store'",
    'const payload = await response.json()',
    'this.applyNotificationDeckSnapshot(payload)',
    'finally {',
    'this.notificationDeckRefreshing = false',
):
    if needle not in navbar:
        raise SystemExit(f'Navbar is missing snapshot refresh lifecycle: {needle}')

for forbidden in (
    'notificationDeckRefreshPending',
    'notificationDeckRefreshInFlight',
    'finishNotificationDeckRefresh()',
    'window.htmx.ajax',
    'await Promise.race([request, timeout])',
    'await this.notificationDeckRefreshInFlight',
    "window.htmx.trigger(document.body, 'kaori:notification-deck-refresh')",
):
    if forbidden in navbar:
        raise SystemExit(f'Legacy or unbounded refresh state remains in navbar: {forbidden}')

for needle in (
    "document.getElementById('notification-deck-active-job-list')",
    "document.getElementById('notification-deck-notifications-content')",
    'activityTarget.innerHTML = payload.activity_html',
    'notificationsTarget.innerHTML = payload.notifications_html',
    'window.htmx?.process(notificationsTarget)',
    'window.renderLocalOperationalActivities?.()',
):
    if needle not in navbar:
        raise SystemExit(f'Snapshot application is missing stable-slot update: {needle}')

for needle in (
    'from flask import Blueprint, jsonify,',
    'def _render_refresh_snapshot()',
    'never wait for queued workers to finish',
    "'active_count': int(context.get('active_count', 0))",
    "'unread_count': int(context.get('unread_count', 0))",
    "'activity_html': render_template(",
    "'notifications_html': render_template(",
    "@notifications_bp.get('/panel/refresh')",
    'return _render_refresh_snapshot()',
    "response.headers['Cache-Control'] = 'no-store, max-age=0'",
):
    if needle not in routes:
        raise SystemExit(f'Notification routes are missing JSON snapshot contract: {needle}')

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

if "elif job.progress_mode == 'queued'" not in component:
    raise SystemExit('Queued jobs must use a static progress marker.')
if 'w-1/3 rounded-full bg-kaori-primary/60' not in component:
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
    'aria-label="Notification center sections"',
    'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1',
    "selected_view == 'activity'",
    "selected_view == 'notifications'",
    'data-server-activity-item',
):
    if needle not in page_tabs:
        raise SystemExit(f'Notifications page is not aligned with deck tabs: {needle}')

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
    'KAORI Notification Deck audit passed: Activity and Notifications use a five-second '
    'read-only JSON snapshot, manual refresh aborts older polling and always releases its '
    'spinner, queued workers never block refresh, and stable content slots prevent flicker.'
)
