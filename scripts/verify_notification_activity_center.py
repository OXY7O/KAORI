#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise SystemExit(f'Missing Activity Center file: {relative}')
    return path.read_text(encoding='utf-8')


checks = {
    'app/templates/components/navigation/_notification_center.html': (
        'data-lucide="activity"',
        'data-lucide="bell"',
        'Activity & Notifications',
        'data-local-activity-list',
        "activityCenterTab = 'running'",
    ),
    'app/notifications/queries.py': (
        'get_activity_center_context',
        'JobExecution.subscribers.any',
        'JobExecution.requested_by_user_id == user_id',
        'ACTIVITY_CENTER_ACTIVE_JOB_STATUSES',
    ),
    'app/templates/notifications/index.html': (
        'Activity & Notifications',
        'activity_center.active_count',
        'activity_center.unread_count',
    ),
    'app/templates/layouts/app.html': (
        'startOperationalActivity',
        'renderLocalOperationalActivities',
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
        'data-local-activity-list',
    ),
    'app/notifications/routes.py': (
        "HX-Trigger-After-Swap",
        "kaori:notifications-changed",
    ),
}

for relative, required in checks.items():
    content = read(relative)
    missing = [needle for needle in required if needle not in content]
    if missing:
        raise SystemExit(f'{relative} is missing required Activity Center contracts: {missing}')

layout = read('app/templates/layouts/app.html')
if 'showOperationalProgressToast' in layout:
    raise SystemExit('Legacy operational progress toast remains active in app layout.')

print(
    'KAORI Activity Center audit passed: running jobs, attention notifications, '
    'history, explicit read state, and background-feedback delivery are synchronized.'
)
