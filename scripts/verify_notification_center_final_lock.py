#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1.md',
    'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1_1.md',
    'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1_2.md',
    'docs/design/audits/KAORI_NOTIFICATION_CENTER_FINAL_LOCK_AUDIT_2026_08_08.md',
    'docs/design/audits/KAORI_NOTIFICATION_CENTER_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md',
    'docs/design/audits/KAORI_NOTIFICATION_CENTER_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md',
    'docs/design/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md',
    'app/templates/notifications/index.html',
    'app/templates/notifications/partials/_center_page_content.html',
    'app/templates/notifications/components/_activity_center_items.html',
    'app/templates/components/navigation/_notification_center.html',
    'app/templates/components/framed_workspace_tabs.html',
    'app/notifications/routes.py',
    'app/notifications/queries.py',
    'app/notifications/event_catalog.py',
    'app/notifications/presentation.py',
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
    catalog = read('app/notifications/event_catalog.py')
    presentation = read('app/notifications/presentation.py')
    navigation = read('app/common/navigation.py')
    quality_gate = read('scripts/quality_gate.sh')

    for required in (
        'Notification Center',
        'Personal Operations',
        'Personal Inbox',
        'Notification Posture',
        'Unread',
        'Active Work',
        'Activity Audit',
        "url_for('notifications.activity_log')",
    ):
        if required not in page:
            errors.append(f'Notification Center hero/boundary contract missing: {required}')

    if 'Activity Audit remains the system-wide administrative evidence view.' in page:
        errors.append('Notification Center hero still renders the retired Activity Audit helper strip')

    for required in (
        'Personal Operations Inbox',
        'components/framed_workspace_tabs.html',
        'framed_workspace_tabs.render_navigation(',
        'components/table.html',
        'components/table_label.html',
        'components/loading_bar.html',
        'Notification Evidence',
        'Lifecycle Boundary',
        'Delivery Boundary',
        'Administrative Evidence',
        'Notification Register',
        'Search Notifications',
        'All Categories',
        'All Statuses',
        'All States',
        'notification-center-loading',
        'Previous',
        'Next',
        'Rows Per Page',
        "pagination_ui.resource_name('Notifications'",
        "url_for('platform_operations.data_lifecycle.index', tab='policies', domain='operational_activity')",
        "url_for('jobs.executions')",
    ):
        if required not in content:
            errors.append(f'Notification Center workspace contract missing: {required}')

    if content.index('Lifecycle Boundary') > content.index('Notification Register'):
        errors.append('Lifecycle Boundary must appear before the Notification Register')
    if 'role="tablist"' in content:
        errors.append('Notification Center must use shared server-owned framed navigation')
    if 'macro render_navigation' not in framed_tabs or 'framed-workspace-v2-server' not in framed_tabs:
        errors.append(
            'shared framed workspace component must own server-backed Notification Center navigation geometry'
        )
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
        'Notification.deck_visible.is_(True)',
        "Notification.event_type != 'authentication'",
        "'notification_filters': {",
        "'notification_category_options': [",
        "status=request.args.get('status', 'all')",
        "read_state=request.args.get('read_state', 'all')",
        "category=request.args.get('category', 'all')",
        "search=request.args.get('search', '')",
    ):
        source = routes if 'request.args' in required else queries
        if required not in source:
            errors.append(f'Notification Center query/filter contract missing: {required}')

    for required in (
        "'configmap_management': 'ConfigMap Management'",
        "'tls_certificate': 'TLS Certificate'",
        "'secret_management': 'Secret Management'",
        "'integrations': 'Integrations'",
        "'platform_operations': 'Platform Operations'",
        "'access': 'Access'",
        "'settings': 'Settings'",
        "'configmap': 'ConfigMap'",
        "'tls': 'TLS'",
        "'rbac': 'RBAC'",
        "'k8s': 'K8s'",
    ):
        if required not in catalog:
            errors.append(f'Notification category/Title Case contract missing: {required}')

    if 'standardize_activity_title(' not in presentation:
        errors.append('Notification titles must use the Title Case display normalizer')
    if 'get_notification_center_page_context(' not in routes or "per_page=_request_int('per_page', 5)" not in routes:
        errors.append('Notification Center route must use paginated user-scoped page context with default Rows=5')
    if "'notifications.center': 'Notification Center'" not in navigation:
        errors.append('Notification Center navigation label must be canonical')
    if 'verify_operational_feedback_coverage.py' not in quality_gate:
        errors.append('Operational Feedback Coverage verifier must be release-gated')

    if errors:
        print('KAORI Notification Center Final Lock FAILED')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Notification Center Final Lock v1.2')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
