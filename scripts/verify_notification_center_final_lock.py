#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1.md',
    'docs/design/audits/KAORI_NOTIFICATION_CENTER_FINAL_LOCK_AUDIT_2026_08_08.md',
    'app/templates/notifications/index.html',
    'app/templates/notifications/partials/_center_page_content.html',
    'app/templates/notifications/components/_activity_center_items.html',
    'app/templates/components/navigation/_notification_center.html',
    'app/templates/components/framed_workspace_tabs.html',
    'app/notifications/routes.py',
    'app/notifications/queries.py',
    'app/notifications/service.py',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f'missing Notification Center lock artifact: {relative}')

    page = read('app/templates/notifications/index.html')
    content = read('app/templates/notifications/partials/_center_page_content.html')
    items = read('app/templates/notifications/components/_activity_center_items.html')
    deck = read('app/templates/components/navigation/_notification_center.html')
    framed_tabs = read('app/templates/components/framed_workspace_tabs.html')
    routes = read('app/notifications/routes.py')
    queries = read('app/notifications/queries.py')
    navigation = read('app/common/navigation.py')

    for required in (
        'Notification Center',
        'Personal Operations',
        'Center Boundary',
        'Active Work',
        'Activity Audit',
        "url_for('notifications.activity_log')",
    ):
        if required not in page:
            errors.append(f'Notification Center hero/boundary contract missing: {required}')

    for required in (
        'Personal Operations Inbox',
        'components/framed_workspace_tabs.html',
        'framed_workspace_tabs.render_navigation(',
        'Notifications',
        'Active Work',
        'components/pagination.html',
        'Rows Per Page',
        "pagination_ui.resource_name('Notifications'",
        'Lifecycle Boundary',
        'Transient toasts are not persisted and are not archived.',
        "url_for('platform_operations.data_lifecycle.index', tab='policies', domain='operational_activity')",
        "url_for('jobs.executions')",
    ):
        if required not in content:
            errors.append(f'Notification Center workspace contract missing: {required}')

    if 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1' in content:
        errors.append('full Notification Center must not use the old brand-heavy segmented track')
    if 'role="tablist"' in content:
        errors.append('full Notification Center must use the shared server-owned framed navigation, not a page-local tablist')
    if 'macro render_navigation' not in framed_tabs or 'framed-workspace-v2-server' not in framed_tabs:
        errors.append('shared framed workspace component must own server-backed Notification Center navigation geometry')
    if 'border-kaori-primary/20 bg-kaori-soft' in items:
        errors.append('unread Notification cards must use neutral KAORI surfaces')
    if 'components/progress_bar.html' not in items or 'progress_bar.determinate(' not in items:
        errors.append('Notification Center Active Work must use shared determinate progress presentation')

    for required in (
        'Active Work',
        'rounded-xl border border-outline-default bg-surface-hover p-1',
        "notificationDeckTab === 'activity'",
        "notificationDeckTab === 'notifications'",
    ):
        if required not in deck:
            errors.append(f'Notification Deck contract missing: {required}')

    for required in (
        'def get_notification_center_page_context(',
        '_user_notification_query(user_id)',
        'ACTIVITY_PER_PAGE_OPTIONS',
        "Notification.deck_visible.is_(True)",
        "Notification.event_type != 'authentication'",
        "'notification_pagination': {",
    ):
        if required not in queries:
            errors.append(f'Notification Center pagination/scope contract missing: {required}')

    if 'get_notification_center_page_context(' not in routes or "per_page=_request_int('per_page', 5)" not in routes:
        errors.append('Notification Center route must use paginated user-scoped page context with default Rows=5')
    if "'notifications.center': 'Notification Center'" not in navigation:
        errors.append('Notification Center navigation label must be canonical')

    if errors:
        print('KAORI Notification Center Final Lock FAILED')
        for error in errors:
            print(f'- {error}')
        return 1

    print('KAORI Notification Center Final Lock v1 passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
