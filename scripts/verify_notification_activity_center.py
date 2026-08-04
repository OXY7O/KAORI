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
    'app/templates/notifications/partials/_notification_deck_refresh.html',
    'app/templates/notifications/partials/_notification_deck_oob.html',
    'app/templates/notifications/components/_activity_center_items.html',
    'app/notifications/routes.py',
    'app/notifications/queries.py',
    'app/notifications/service.py',
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
refresh = read('app/templates/notifications/partials/_notification_deck_refresh.html')
oob = read('app/templates/notifications/partials/_notification_deck_oob.html')
routes = read('app/notifications/routes.py')
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

for forbidden in (
    'hx-trigger="every 15s',
    'kaori:notification-deck-refresh-complete',
    'notificationDeckRefreshPending',
    "url_for('notifications.panel_activity')",
    "url_for('notifications.panel_notifications')",
):
    if forbidden in shell or forbidden in navbar:
        raise SystemExit(f'Legacy concurrent refresh contract remains active: {forbidden}')

for needle in (
    'role="tablist"',
    'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1',
    "notificationDeckTab === 'activity' ? 'bg-surface-card text-kaori-primary shadow-sm'",
    ":class=\"notificationDeckTab === 'activity' ? 'block' : 'hidden'\"",
    '@click="refreshNotificationDeck(true)"',
    ':disabled="notificationDeckRefreshing"',
    "notificationDeckRefreshing ? 'animate-spin' : ''",
    'border border-kaori-primary bg-kaori-primary text-white',
    'Auto refresh every 15 seconds',
    'Refresh failed. Auto refresh will retry.',
):
    if needle not in shell:
        raise SystemExit(f'Notification Deck is missing professional refresh/tab contract: {needle}')

for needle in (
    'notificationDeckRefreshing: false',
    'notificationDeckRefreshError: false',
    'notificationDeckRefreshInFlight: null',
    'window.setInterval(() =>',
    '}, 15000)',
    'async refreshNotificationDeck(manual = true)',
    "window.htmx.ajax('GET', refreshUrl",
    'await Promise.race([request, timeout])',
    'finally {',
    'this.notificationDeckRefreshing = false',
):
    if needle not in navbar:
        raise SystemExit(f'Navbar is missing serialized refresh lifecycle: {needle}')

for forbidden in (
    'notificationDeckRefreshPending',
    'finishNotificationDeckRefresh()',
    "window.htmx.trigger(document.body, 'kaori:notification-deck-refresh')",
):
    if forbidden in navbar:
        raise SystemExit(f'Unbounded refresh state remains in navbar: {forbidden}')

for needle in (
    'data-local-activity-list',
    'id="notification-deck-active-job-list"',
    'data-running-empty',
    'data-activity-surface',
    'data-activity-count-label',
):
    if needle not in activity:
        raise SystemExit(f'Activity panel is missing stable-slot contract: {needle}')
for forbidden in ('data-activity-dynamic-source', 'visible_jobs', 'inventory_sync_all', 'inventory_sync_cluster'):
    if forbidden in activity:
        raise SystemExit(f'Activity panel still contains unstable/filtered source: {forbidden}')
if 'data-server-activity-item' not in activity_jobs:
    raise SystemExit('Activity job fragment does not expose stable server activity items.')

for needle in (
    'id="notification-deck-active-job-list"',
    'id="notification-deck-notifications-content"',
    'hx-swap-oob="innerHTML"',
    '_notification_deck_activity_jobs.html',
    '_notification_deck_notifications.html',
    '_notification_deck_oob.html',
):
    if needle not in refresh:
        raise SystemExit(f'Combined refresh payload is missing contract: {needle}')

for needle in (
    "target='#notification-deck-notifications-content'",
    'hx-target="#notification-deck-notifications-content"',
    'hx-swap="innerHTML"',
):
    if needle not in notifications:
        raise SystemExit(f'Notifications panel is missing stable content target: {needle}')

for needle in (
    "@notifications_bp.get('/panel/refresh')",
    "'notifications/partials/_notification_deck_refresh.html'",
    "response.headers['Cache-Control'] = 'no-store, max-age=0'",
):
    if needle not in routes:
        raise SystemExit(f'Notification routes are missing combined refresh contract: {needle}')

for needle in (
    "surface.querySelectorAll('[data-server-activity-item]').length",
    "document.getElementById('notification-deck-active-count')",
    "emptyState.classList.toggle('hidden', totalCount > 0)",
):
    if needle not in layout:
        raise SystemExit(f'Activity surface reconciliation is missing: {needle}')
for forbidden in ('data-activity-dynamic-source', 'activityServerCount'):
    if forbidden in layout:
        raise SystemExit(f'Legacy activity reconciliation remains: {forbidden}')

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
    raise SystemExit('OOB badge fragment must update four stable badge targets.')
if 'showOperationalProgressToast' in layout:
    raise SystemExit('Legacy operational progress toast remains active in app layout.')

print(
    'KAORI Notification Deck audit passed: Activity and Notifications are refreshed '
    'together every 15 seconds through one serialized request, manual refresh has a '
    'bounded loading state, stable activity slots prevent flicker, and the page/deck '
    'segmented controls remain aligned.'
)
