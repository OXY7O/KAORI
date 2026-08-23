from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_shared_summary_surfaces_follow_reporting_posture_pattern() -> None:
    recommendation = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    catalog = read('app/templates/intelligence/partials/_catalog_summary.html')
    alert_summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    for template in (recommendation, catalog, alert_summary):
        assert 'intelligence_ui.posture_panel(' in template
        assert 'intelligence_ui.posture_metric(' in template
        assert 'grid divide-y divide-outline-subtle sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4' in template


def test_operator_direction_uses_clear_surface() -> None:
    detail = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    assert 'bg-kaori-mist/50' not in detail
    assert 'Operator Direction' in detail
    assert 'bg-surface-card' in detail


def test_resolved_modal_uses_simpler_active_alert_aligned_sections() -> None:
    modal = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    assert 'Resolution Summary' in modal
    assert 'Recovery Steps & References' in modal
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in modal


def test_copy_is_shortened_on_routing_catalog_and_automation_control() -> None:
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    catalog_summary = read('app/templates/intelligence/partials/_catalog_summary.html')
    catalog_page = read('app/templates/intelligence/rule_catalog.html')
    automation = read('app/intelligence/automation_control/overview.py')

    assert (
        'Control which validated Notification Channels receive promoted Alert Cases, how often alerts repeat, and when verified recovery is delivered.'
        in routing
    )
    assert (
        'Review the current catalog scope before scanning definitions, evaluator readiness, and imported-signal coverage.'
        in catalog_summary
    )
    assert (
        'Search rule ownership, provider coverage, evaluator readiness, source boundaries, severity, and operator response.'
        in catalog_page
    )
    assert 'Governance stays writable while infrastructure execution remains fail-closed.' in automation
    assert 'lifecycle events are covered; ' in automation


def test_telegram_notifications_keep_html_and_absolute_action_link_fallback() -> None:
    provider = read('app/integrations/delivery/notification_channels/providers/telegram.py')
    notifications = read('app/intelligence/alert_intelligence/notifications.py')
    assert "payload['parse_mode'] = 'HTML'" in provider
    assert 'Open in KAORI' in provider
    assert 'def _notification_action_url(path: str) -> str | None:' in notifications
