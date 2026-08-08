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
    assert 'Center Boundary' in page
    assert 'Activity Audit' in page
    assert 'remains the administrative system-wide evidence view.' in page
    assert 'Notifications' in content
    assert 'Active Work' in content
    assert 'Personal Operations Inbox' in content
    assert "'notifications.center': 'Notification Center'" in navigation


def test_full_center_uses_standard_pagination_and_user_scope() -> None:
    routes = read('app/notifications/routes.py')
    queries = read('app/notifications/queries.py')
    content = read('app/templates/notifications/partials/_center_page_content.html')

    assert 'get_notification_center_page_context(' in routes
    assert "per_page=_request_int('per_page', 5)" in routes
    assert 'def get_notification_center_page_context(' in queries
    assert '_user_notification_query(user_id)' in queries
    assert 'Notification.deck_visible.is_(True)' in queries
    assert "Notification.event_type != 'authentication'" in queries
    assert "'notification_pagination': {" in queries
    assert 'components/pagination.html' in content
    assert 'aria-label="Rows Per Page"' in content
    assert "pagination_ui.resource_name('Notifications'" in content
    assert "{'view': 'notifications', 'per_page': pager.per_page}" in content
    assert "center_refresh_url = url_for('notifications.center', view=selected_view, page=pager.page, per_page=pager.per_page)" in content


def test_notification_center_uses_quiet_kaori_surfaces() -> None:
    content = read('app/templates/notifications/partials/_center_page_content.html')
    items = read('app/templates/notifications/components/_activity_center_items.html')
    deck = read('app/templates/components/navigation/_notification_center.html')
    framed_tabs = read('app/templates/components/framed_workspace_tabs.html')

    assert 'components/framed_workspace_tabs.html' in content
    assert 'framed_workspace_tabs.render_navigation(' in content
    assert 'role="tablist"' not in content
    assert 'border-outline-default bg-surface-hover px-4 pt-4' in framed_tabs
    assert 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1' not in content
    assert 'border-outline-strong bg-surface-subtle' in items
    assert 'border-kaori-primary/20 bg-kaori-soft' not in items
    assert 'components/progress_bar.html' in items
    assert 'progress_bar.determinate(' in items
    assert 'rounded-xl border border-outline-default bg-surface-hover p-1' in deck
    assert 'Active Work' in deck


def test_notification_center_exposes_canonical_runtime_and_lifecycle_boundaries() -> None:
    content = read('app/templates/notifications/partials/_center_page_content.html')

    assert "url_for('jobs.executions')" in content
    assert 'this page does not create a second execution registry.' in content
    assert 'Lifecycle Boundary' in content
    assert "domain='operational_activity'" in content
    assert 'Transient toasts are not persisted and are not archived.' in content


def test_notification_center_final_lock_is_documented_and_release_gated() -> None:
    assert (ROOT / 'docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_NOTIFICATION_CENTER_FINAL_LOCK_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'scripts/verify_notification_center_final_lock.py').exists()
    assert 'verify_notification_center_final_lock.py' in read('scripts/quality_gate.sh')
