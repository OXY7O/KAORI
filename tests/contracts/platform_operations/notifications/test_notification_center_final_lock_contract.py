from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_notification_center_is_personal_and_distinct_from_activity_audit() -> None:
    page = read('app/templates/platform_operations/notifications/index.html')
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
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
    routes = read('app/platform_operations/notifications/routes.py')
    queries = read('app/platform_operations/notifications/queries.py')
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

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


def test_notification_page_size_uses_one_change_request_and_preserves_filters() -> None:
    from jinja2 import Environment

    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
    pagination = read('app/static/js/pagination.js')
    routes = read('app/platform_operations/notifications/routes.py')
    queries = read('app/platform_operations/notifications/queries.py')

    Environment().parse(content)
    rows = content.split('id="notification-center-per-page"', 1)[0].rsplit('<form method="get"', 1)[1]
    rows += content.split('id="notification-center-per-page"', 1)[1].split('</form>', 1)[0]
    for token in (
        'hx-trigger="change"',
        'hx-target="#activity-notification-page"',
        'hx-select="#activity-notification-page"',
        'hx-swap="outerHTML"',
        'hx-push-url="true"',
        'hx-sync="#activity-notification-page:replace"',
        'name="view" value="notifications"',
        'name="page" value="1"',
        'name="search"',
        'name="category"',
        'name="status"',
        'name="read_state"',
        'name="per_page"',
        'Apply Rows',
    ):
        assert token in rows
    assert 'data-kaori-auto-submit' not in rows
    assert 'control.form.requestSubmit()' in pagination  # Existing shared fallback stays unchanged.
    assert 'hx-sync="this:drop"' in content
    assert "per_page=_request_int('per_page', 5)" in routes
    assert 'ACTIVITY_PER_PAGE_OPTIONS = (5, 10, 25, 50)' in read('app/platform_operations/notifications/constants.py')
    assert 'per_page=normalized_per_page' in queries
    assert 'per_page=pager.per_page' in content
    assert 'option == pager.per_page' in content


def test_notification_center_evidence_context_precedes_register() -> None:
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

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


def test_notification_center_uses_canonical_title_guides_and_concise_evidence_copy() -> None:
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

    assert 'components/info_tip.html' in content
    assert content.count("variant='guide'") == 2
    for title, guide_id in (
        ('Personal Operations Inbox', 'notification-center-personal-inbox-guide'),
        ('Notification Register', 'notification-center-register-guide'),
    ):
        heading = content.index(f'>{title}</h')
        guide = content.index(f"'{guide_id}'", heading)
        assert guide < content.index('</div>', heading)
    assert 'Transient toasts remain outside Data Lifecycle.' in content
    assert 'Activity Audit shows system-wide notification evidence.' in content
    assert 'Only persisted outcomes appear here. Transient toasts' not in content
    assert 'Activity Audit remains the system-wide evidence view for authorized administrators.' not in content


def test_notification_register_filter_actions_keep_title_and_guide_first() -> None:
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

    title = content.index('>Notification Register</h3>')
    guide = content.index("'notification-center-register-guide'", title)
    clear_action = content.index('registry_ui.clear_filters_action(', guide)
    clear_options = content[clear_action : content.index(') }}', clear_action)]
    assert title < guide < clear_action
    assert 'lead=false' in clear_options
    assert "push_url='true'" in clear_options
    assert "target='#activity-notification-page'" in clear_options
    assert '{% if filter_active %}' in content[guide:clear_action]


def test_notification_tabs_use_shared_semantic_empty_states() -> None:
    from jinja2 import Environment

    page = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
    shared = read('app/templates/components/states/_empty_state.html')
    runtime = read('app/static/js/application_shell.js')

    Environment().parse(page)
    assert page.count('{% include "components/states/_empty_state.html" %}') == 2
    assert 'data-kaori-empty-state' in shared
    assert "empty_state_variant='panel'" in page
    assert "empty_state_label='Queue Clear'" in page
    assert "empty_state_tone='normal'" in page
    assert "empty_state_title='No Active Work'" in page
    assert 'Queued and running jobs or active page operations will appear here automatically.' in page
    assert 'data-running-empty class="{% if active_jobs %}hidden{% endif %}"' in page
    assert "surface.querySelectorAll('[data-running-empty]')" in runtime
    assert "emptyState.classList.toggle('hidden', totalCount > 0)" in runtime

    assert "empty_state_label='No Results' if filter_active else 'No Data'" in page
    assert "empty_state_title='No Matching Notifications' if filter_active else 'No Notifications Yet'" in page
    assert 'Adjust the filters to find matching notifications.' in page
    assert 'Persistent account notifications will appear here after KAORI commits operational outcomes.' in page
    assert page.index("empty_state_label='No Results'") < page.index(
        '<footer class="{{ pagination_ui.footer_classes() }}">'
    )
    assert 'pager.total' in page
    assert "pagination_ui.resource_name('Notifications'" in page
    assert 'class="px-5 py-12 text-center"' not in page


def test_notification_center_uses_quiet_kaori_surfaces() -> None:
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
    items = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    deck = read('app/templates/components/navigation/_notification_center.html')
    framed_tabs = read('app/templates/components/framed_workspace_tabs.html')

    assert 'components/framed_workspace_tabs.html' in content
    assert 'framed_workspace_tabs.render_navigation(' in content
    assert 'role="tablist"' not in content
    assert 'bg-surface-hover px-4 pt-4' in framed_tabs
    assert 'gap-2 border-b border-outline-default' in framed_tabs
    assert 'components/progress_bar.html' in items
    assert 'progress_bar.job_progress(' in items
    assert 'progress_bar.determinate(' not in items
    assert 'rounded-xl border border-outline-default bg-surface-hover p-1' in deck
    assert 'Active Work' in deck


def test_notification_center_history_uses_kaori_table_contract() -> None:
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

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
    presentation = read('app/platform_operations/notifications/presentation.py')
    catalog = read('app/definitions/catalogs/platform_operations/notifications/event_categories.yaml')
    catalog_py = read('app/platform_operations/notifications/event_catalog.py')
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

    assert 'standardize_activity_title(' in presentation
    for token in (
        "'configmap': 'ConfigMap'",
        "'tls': 'TLS'",
        "'rbac': 'RBAC'",
        "'k8s': 'Kubernetes'",
    ):
        assert token in catalog_py
    for token in (
        'configmap_management:',
        'label: ConfigMap Management',
        'tls_certificate:',
        'label: TLS Certificate',
        'secret_management:',
        'label: Secret Management',
        'integrations:',
        'label: Integrations',
        'platform_operations:',
        'label: Platform Operations',
        'access:',
        'label: Access',
        'settings:',
        'label: Settings',
    ):
        assert token in catalog
    assert '{{ notification.category_label }}' in content


def test_notification_center_exposes_canonical_runtime_and_lifecycle_boundaries() -> None:
    content = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')

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


def test_notification_categories_use_persisted_source_controlled_classification() -> None:
    queries = read('app/platform_operations/notifications/queries.py')
    catalog = read('app/definitions/catalogs/platform_operations/notifications/event_categories.yaml')
    writer = read('app/platform_operations/notifications/writer.py')
    assert 'Notification.category_key == normalized_category' in queries
    assert 'kubernetes_tls_secret_' in catalog
    assert 'kubernetes_secret_' in catalog
    assert 'notification.category_key = event_category_key(event_type)' in writer


def test_notification_center_service_forwards_all_filter_arguments() -> None:
    service = read('app/platform_operations/notifications/service.py')

    signature = service.split('def get_notification_center_page_context(', 1)[1].split(') -> dict[str, Any]:', 1)[0]
    body = service.split('def get_notification_center_page_context(', 1)[1].split('def mark_notification_read(', 1)[0]

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
