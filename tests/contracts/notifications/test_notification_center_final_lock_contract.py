from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_notification_center_is_personal_and_distinct_from_activity_audit() -> None:
    page = read('app/templates/notifications/index.html')
    content = read('app/templates/notifications/partials/_center_page_content.html')
    navigation = read('app/common/navigation.py')

    assert '<h1 class="{{ page_hero.title_classes() }}">Notification Center</h1>' in page
    assert 'Personal Operations' in page
    assert 'Personal Inbox' in page
    assert 'Notification Posture' in page
    assert 'Activity Audit' in page
    assert 'Activity Audit remains the system-wide administrative evidence view.' not in page
    assert 'Notifications' in content
    assert 'Active Work' in content
    assert 'Personal Operations Inbox' in content
    assert "'notifications.center': 'Notification Center'" in navigation


def test_full_center_uses_standard_filters_loading_and_pagination() -> None:
    routes = read('app/notifications/routes.py')
    queries = read('app/notifications/queries.py')
    content = read('app/templates/notifications/partials/_center_page_content.html')

    assert 'get_notification_center_page_context(' in routes
    assert "per_page=_request_int('per_page', 5)" in routes
    assert "status=request.args.get('status', 'all')" in routes
    assert "read_state=request.args.get('read_state', 'all')" in routes
    assert "category=request.args.get('category', 'all')" in routes
    assert "search=request.args.get('search', '')" in routes
    assert '_user_notification_query(user_id)' in queries
    assert "'notification_filters': {" in queries
    assert "'notification_category_options': [" in queries
    assert 'components/pagination.html' in content
    assert 'components/loading_bar.html' in content
    assert 'Search Notifications' in content
    assert 'All Categories' in content
    assert 'All Statuses' in content
    assert 'All States' in content
    assert 'notification-center-loading' in content
    assert 'aria-label="Rows Per Page"' in content
    assert 'Previous' in content
    assert 'Next' in content
    assert "pagination_ui.resource_name('Notifications'" in content


def test_notification_center_evidence_context_precedes_register() -> None:
    content = read('app/templates/notifications/partials/_center_page_content.html')

    for token in (
        'Notification Evidence',
        'Lifecycle Boundary',
        'Delivery Boundary',
        'Administrative Evidence',
        'Notification Register',
    ):
        assert token in content
    assert content.index('Lifecycle Boundary') < content.index('Notification Register')
    assert 'Persistent notifications share the Activity Audit retention policy.' in content
    assert 'Transient toasts remain outside Data Lifecycle.' in content


def test_notification_center_uses_quiet_kaori_surfaces() -> None:
    content = read('app/templates/notifications/partials/_center_page_content.html')
    items = read('app/templates/notifications/components/_activity_center_items.html')
    deck = read('app/templates/components/navigation/_notification_center.html')
    framed_tabs = read('app/templates/components/framed_workspace_tabs.html')

    assert 'components/framed_workspace_tabs.html' in content
    assert 'framed_workspace_tabs.render_navigation(' in content
    assert 'role="tablist"' not in content
    assert 'border-outline-default bg-surface-hover px-4 pt-4' in framed_tabs
    assert 'components/progress_bar.html' in items
    assert 'progress_bar.job_progress(' in items
    assert 'progress_bar.determinate(' not in items
    assert 'rounded-xl border border-outline-default bg-surface-hover p-1' in deck
    assert 'Active Work' in deck


def test_notification_center_history_uses_kaori_table_contract() -> None:
    content = read('app/templates/notifications/partials/_center_page_content.html')

    for token in (
        'components/table.html',
        'components/table_label.html',
        'Notification',
        'Event',
        'Status',
        'Received',
        'State',
        'Action',
        'table_ui.table_classes(',
        'table_label.status_label(',
    ):
        assert token in content


def test_notification_center_title_case_and_category_contract() -> None:
    presentation = read('app/notifications/presentation.py')
    catalog = read('app/notifications/event_catalog.py')
    content = read('app/templates/notifications/partials/_center_page_content.html')

    assert 'standardize_activity_title(' in presentation
    for token in (
        "'configmap': 'ConfigMap'",
        "'tls': 'TLS'",
        "'rbac': 'RBAC'",
        "'k8s': 'K8s'",
        "'configmap_management': 'ConfigMap Management'",
        "'tls_certificate': 'TLS Certificate'",
        "'secret_management': 'Secret Management'",
        "'integrations': 'Integrations'",
        "'platform_operations': 'Platform Operations'",
        "'access': 'Access'",
        "'settings': 'Settings'",
    ):
        assert token in catalog
    assert '{{ notification.category_label }}' in content


def test_notification_center_exposes_canonical_runtime_and_lifecycle_boundaries() -> None:
    content = read('app/templates/notifications/partials/_center_page_content.html')

    assert "url_for('jobs.executions')" in content
    assert 'Canonical queued and running work mirrored from Jobs &amp; Executions.' in content
    assert "domain='operational_activity'" in content


def test_notification_center_final_lock_is_documented_and_release_gated() -> None:
    assert (ROOT / 'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1_2.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_NOTIFICATION_CENTER_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'scripts/verify_notification_center_final_lock.py').exists()
    assert 'verify_notification_center_final_lock.py' in read('scripts/quality_gate.sh')


def test_secret_management_filter_excludes_tls_certificate_events() -> None:
    queries = read('app/notifications/queries.py')
    assert "~Notification.event_type.like('kubernetes_tls_secret_%')" in queries


def test_notification_center_service_forwards_all_filter_arguments() -> None:
    service = read('app/notifications/service.py')

    signature = service.split('def get_notification_center_page_context(', 1)[1].split(') -> dict[str, Any]:', 1)[0]
    body = service.split('def get_notification_center_page_context(', 1)[1].split(
        'def get_notification_activity_context(', 1
    )[0]

    for token in (
        "status: str = 'all'",
        "read_state: str = 'all'",
        "category: str = 'all'",
        "search: str = ''",
    ):
        assert token in signature

    for token in (
        'status=status',
        'read_state=read_state',
        'category=category',
        'search=search',
    ):
        assert token in body
