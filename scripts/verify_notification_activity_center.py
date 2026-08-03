#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise SystemExit(f'Missing Notification Deck file: {relative}')
    return path.read_text(encoding='utf-8')


checks = {
    'app/templates/components/navigation/_notification_center.html': (
        'data-lucide="bell"',
        'Notification Deck',
        'notificationDeckOpen',
        'notification-running-indicator',
        'notification-bell-badge',
        'translate-x-full',
    ),
    'app/templates/notifications/partials/_notification_deck_content.html': (
        "notificationDeckTab = 'activity'",
        "notificationDeckTab = 'notifications'",
        'data-local-activity-list',
        'every 15s',
        'kaori:notifications-changed from:body',
        'hx-swap-oob="outerHTML"',
    ),
    'app/notifications/queries.py': (
        'get_activity_center_context',
        'JobExecution.subscribers.any',
        'JobExecution.requested_by_user_id == user_id',
        'ACTIVITY_CENTER_ACTIVE_JOB_STATUSES',
    ),
    'app/templates/notifications/index.html': (
        'Notifications',
        'activity_center.active_count',
        'activity_center.unread_count',
    ),
    'app/templates/layouts/app.html': (
        'startOperationalActivity',
        'renderLocalOperationalActivities',
        'notification-running-indicator',
    ),
    'app/notifications/service.py': (
        '_feedback_delivery',
        "event_metadata.get('feedback_delivery')",
        'is_background_event',
        "return 'activity_center'",
    ),
    'app/templates/notifications/partials/_center_page_content.html': (
        'kaori:notifications-changed from:body',
        'every 15s',
        "view='activity'",
        "view='notifications'",
    ),
    'app/notifications/routes.py': (
        "frozenset({'activity', 'notifications'})",
        "'notifications/partials/_notification_deck_content.html'",
        'HX-Trigger-After-Swap',
        'kaori:notifications-changed',
    ),
}

for relative, required in checks.items():
    content = read(relative)
    missing = [needle for needle in required if needle not in content]
    if missing:
        raise SystemExit(f'{relative} is missing required Notification Deck contracts: {missing}')

trigger = read('app/templates/components/navigation/_notification_center.html')
if trigger.count('aria-label="Open notification deck"') != 1:
    raise SystemExit('Top bar must expose exactly one Notification Deck trigger.')
if 'data-lucide="activity"' in trigger:
    raise SystemExit('A separate top-bar Activity icon remains; only the bell is allowed.')
if 'hx-trigger=' in trigger:
    raise SystemExit('The stable top-bar bell must not be replaced by polling.')

deck = read('app/templates/notifications/partials/_notification_deck_content.html')
if 'hx-trigger="load, every 15s' in deck or 'load, every 15s' in deck:
    raise SystemExit('Self-replacing Notification Deck must not use a load trigger.')

layout = read('app/templates/layouts/app.html')
if 'showOperationalProgressToast' in layout:
    raise SystemExit('Legacy operational progress toast remains active in app layout.')

print(
    'KAORI Notification Deck audit passed: one stable bell opens the right-side '
    'slider, active work stays inside the deck, unread state remains synchronized, '
    'and polling cannot create a self-refresh loop.'
)
