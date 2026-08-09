from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_activity_audit_uses_bounded_posture_and_access_hero_contract() -> None:
    page = read('app/templates/notifications/activity.html')
    summary = read('app/templates/notifications/partials/_activity_summary_cards.html')
    queries = read('app/notifications/queries.py')

    assert '<h1 class="{{ page_hero.title_classes() }}">Activity Audit</h1>' in page
    assert 'Administrative Evidence' in page
    assert 'Audit Posture' in page
    assert 'Events · 24H' in page
    assert 'Attention · 24H' in page
    assert 'Audit Evidence Overview' in summary
    assert 'Successful · 24H' in summary
    assert 'Actors · 24H' in summary
    assert 'System-Wide Scope' in summary
    assert 'Persistent Evidence' in summary
    assert 'Lifecycle Boundary' in summary
    assert 'Sensitive Data Boundary' in summary
    assert 'cutoff_24h = datetime.now(UTC) - timedelta(hours=24)' in queries
    assert "func.count(func.distinct(func.coalesce(Notification.user_id, 0)))" in queries
    assert 'Unread' not in page
    assert 'Unread Activities' not in summary


def test_activity_register_uses_kaori_filters_loading_table_and_pagination() -> None:
    card = read('app/templates/notifications/partials/_activity_table_card.html')
    content = read('app/templates/notifications/partials/_activity_table_content.html')
    route = read('app/notifications/routes.py')
    queries = read('app/notifications/queries.py')

    for token in (
        'components/table.html',
        'components/loading_bar.html',
        'Activity Register',
        'Search Activity',
        'Category',
        'Status',
        'Actor',
        'Time Range',
        "class=\"grid w-full gap-3 sm:grid-cols-2 xl:grid-cols-5\"",
        "loading_bar.render('operational-activity-loading'",
        'Refreshing Activity Register',
    ):
        assert token in card

    for token in (
        'components/table.html',
        'components/table_label.html',
        'components/pagination.html',
        'Activity',
        'Category',
        'Actor',
        'Status',
        'Recorded',
        'Action',
        'Rows Per Page',
        'Previous',
        'Next',
        "pagination_ui.resource_name('Activities'",
        "resource_detail_modal.detail_button(",
    ):
        assert token in content

    assert "category=request.args.get('category', 'all')" in route
    assert "time_range=request.args.get('time_range', '7d')" in route
    assert 'include_summary=not is_htmx' in route
    assert "event_type=request.args.get('event_type'" not in route
    activity_route = route.split("def activity_log()", 1)[1].split("def activity_detail(", 1)[0]
    assert "read_state=request.args.get('read_state'" not in activity_route
    assert "normalized_time_range = time_range if time_range in _ACTIVITY_TIME_RANGES else '7d'" in queries
    assert "_activity_category_condition(normalized_category)" in queries
    assert "Notification.read_at" not in queries.split('def get_notification_activity_context(', 1)[1].split('def mark_notification_read(', 1)[0]


def test_activity_detail_uses_content_driven_modal_and_curated_evidence() -> None:
    page = read('app/templates/notifications/activity.html')
    detail = read('app/templates/notifications/partials/_activity_detail.html')
    presentation = read('app/notifications/presentation.py')
    routes = read('app/notifications/routes.py')
    service = read('app/notifications/service.py')

    assert "url_for('notifications.activity_detail', notification_id=0)" in page
    assert "dialog_max_width='max-w-5xl'" in page
    assert 'content_driven=true' in page
    assert "@notifications_bp.get('/activity/<int:notification_id>/details')" in routes
    assert 'get_notification_activity_detail(notification_id=notification_id)' in routes
    assert 'def get_notification_activity_detail(' in service

    for token in (
        'Activity Summary',
        'Failure Summary',
        'Execution Evidence',
        'Actor & Access',
        'Target Context',
        'Recorded Changes',
        'Trace References',
        'Technical Evidence',
        'item.created_at|user_datetime',
    ):
        assert token in detail

    assert 'Operational Metadata' not in detail
    assert 'Execution & Trace' not in detail
    assert 'Context & Target' not in detail
    assert 'open_by_default=false' in detail
    assert 'View Technical Evidence' in detail
    assert 'Before' in detail and 'After' in detail
    assert '_ACTIVITY_EXECUTION_EVIDENCE_KEYS' in presentation
    assert '_ACTIVITY_TRACE_REFERENCE_KEYS' in presentation
    assert '_ACTIVITY_TECHNICAL_EVIDENCE_KEYS' in presentation
    assert 'standardize_activity_text(' in presentation
    assert "return 'Name Resolution'" in presentation
    assert "r'\\1***:***@'" in presentation


def test_activity_audit_suppresses_sensitive_metadata_and_keeps_lifecycle_boundary() -> None:
    metadata = read('app/notifications/metadata.py')
    summary = read('app/templates/notifications/partials/_activity_summary_cards.html')
    activity = read('app/templates/notifications/activity.html')

    assert '_SENSITIVE_METADATA_TOKENS' in metadata
    for token in ('password', 'secret', 'token', 'private_key', 'kubeconfig', 'credential_value'):
        assert repr(token) in metadata
    assert '_sensitive_metadata_key(key)' in metadata
    assert '_sensitive_metadata_key(base_key)' in metadata
    assert 'Activity Audit and persistent Notification Center records share the same archive-first policy' in summary
    assert 'Lifecycle boundary:' not in activity
