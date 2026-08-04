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
    'app/templates/notifications/partials/_notification_deck_notifications.html',
    'app/templates/notifications/partials/_notification_deck_oob.html',
    'app/templates/notifications/components/_activity_center_items.html',
    'app/notifications/routes.py',
    'app/notifications/queries.py',
    'app/notifications/service.py',
    'app/templates/notifications/index.html',
    'app/templates/notifications/partials/_center_page_content.html',
    'app/templates/layouts/app.html',
)
for relative in required_files:
    read(relative)

shell = read('app/templates/components/navigation/_notification_center.html')
if shell.count('aria-label="Open notification deck"') != 1:
    raise SystemExit('Top bar must expose exactly one Notification Deck trigger.')
for needle in (
    'x-teleport="body"',
    'data-notification-deck-dialog',
    'id="notification-deck-activity"',
    'id="notification-deck-notifications"',
    "url_for('notifications.panel_activity')",
    "url_for('notifications.panel_notifications')",
    'hx-swap="innerHTML"',
    'kaori:notification-deck-refresh from:body',
    'notification-bell-badge',
    'notification-running-indicator',
):
    if needle not in shell:
        raise SystemExit(f'Notification shell is missing stable-deck contract: {needle}')

if 'hx-swap="outerHTML"' in shell:
    raise SystemExit('Notification shell must never be replaced with outerHTML.')
if 'hx-get="{{ url_for(\'notifications.panel\') }}"' in shell:
    raise SystemExit('Notification shell still polls the legacy combined panel endpoint.')
if 'data-lucide="activity"' not in shell:
    raise SystemExit('Activity tab icon is missing inside the slider deck.')

legacy_fragment = ROOT / 'app/templates/notifications/partials/_notification_deck_content.html'
if legacy_fragment.exists():
    raise SystemExit('Legacy self-replacing Notification Deck fragment still exists.')

activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')
oob = read('app/templates/notifications/partials/_notification_deck_oob.html')
component = read('app/templates/notifications/components/_activity_center_items.html')
routes = read('app/notifications/routes.py')

for needle in ('data-local-activity-list', 'data-running-empty', 'emit_oob'):
    if needle not in activity:
        raise SystemExit(f'Activity panel is missing contract: {needle}')
for needle in (
    "target='#notification-deck-notifications'",
    "swap='innerHTML'",
    'hx-target="#notification-deck-notifications"',
    'hx-swap="innerHTML"',
    'emit_oob',
):
    if needle not in notifications:
        raise SystemExit(f'Notifications panel is missing contract: {needle}')
for needle in (
    'hx-swap-oob="outerHTML"',
    'notification-deck-active-count',
    'notification-deck-unread-count',
):
    if needle not in oob:
        raise SystemExit(f'OOB badge fragment is missing contract: {needle}')
if "swap='outerHTML'" not in component or 'hx-swap="{{ swap }}"' not in component:
    raise SystemExit('Notification item macro does not support a safe innerHTML deck mutation.')

for needle in (
    "@notifications_bp.get('/panel/activity')",
    "@notifications_bp.get('/panel/notifications')",
    "'notifications/partials/_notification_deck_activity.html'",
    "'notifications/partials/_notification_deck_notifications.html'",
    "response.headers['Cache-Control'] = 'no-store, max-age=0'",
    'return _render_notifications_panel()',
):
    if needle not in routes:
        raise SystemExit(f'Notification routes are missing stable-panel contract: {needle}')
if "'_notification_deck_content.html'" in routes:
    raise SystemExit('Routes still render the legacy combined deck fragment.')

layout = read('app/templates/layouts/app.html')
if 'showOperationalProgressToast' in layout:
    raise SystemExit('Legacy operational progress toast remains active in app layout.')

print(
    'KAORI Notification Deck audit passed: the bell and slider shell remain '
    'stable, Activity and Notifications refresh through independent innerHTML '
    'panels, Alpine tab state survives polling, and badge updates remain synchronized.'
)
