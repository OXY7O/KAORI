from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_rule_catalog_supports_dynamic_severity_bands() -> None:
    catalog = read('app/intelligence/catalog.py')
    rules = read('app/definitions/catalogs/intelligence/rules.yaml')
    service = read('app/intelligence/service.py')
    assert 'severity_bands' in rules
    assert 'min_value: 5' in rules and 'severity: info' in rules
    assert 'min_value: 10' in rules and 'severity: warning' in rules
    assert 'min_value: 50' in rules and 'severity: critical' in rules
    assert 'def severity_for_observed_value' in catalog
    assert 'def minimum_severity_band_value' in catalog
    assert 'severity_for_observed_value(restart_rule, max_restarts)' in service
    alerting = read('app/intelligence/recommendation_alerting.py')
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    assert "minimum_severity: warning" in rules
    assert "configured.get('minimum_severity') or 'warning'" in alerting
    assert "observed_severity=str(finding.get('severity') or 'info')" in source
    assert 'Alert Severity Floor' in detail
    assert 'critical_stability_window_minutes: 0' in rules
    assert 'critical_minimum_occurrences: 1' in rules
    assert "default_mode = 'automatic' if eligible else 'manual'" in alerting
    assert "observed_severity=str(finding.get('severity') or 'info')" in source
    assert "observed_severity: str" in source


def test_ack_is_bounded_and_delivery_resumes_when_overdue() -> None:
    model = read('app/models/alert_ops.py')
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    routing = read('app/intelligence/alert_intelligence/routing.py')
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')
    assert 'acknowledgement_expires_at' in model
    assert 'acknowledgement_timeout_minutes' in model
    assert 'acknowledgement_timeout_for_case' in routing
    assert 'expire_acknowledgements_and_notify' in lifecycle
    assert 'acknowledgement_overdue' in lifecycle
    assert 'expire_acknowledgements_and_notify()' in worker


def test_routing_delivery_cadence_is_independent_per_policy_channel() -> None:
    routing = read('app/intelligence/alert_intelligence/routing.py')
    notifications = read('app/intelligence/alert_intelligence/notifications.py')
    assert 'class FiringRoute' in routing
    assert 'def firing_routes' in routing
    assert 'never collapse cadence across channels' in routing
    assert 'def _route_due' in notifications
    assert 'route.channel_id' in notifications
    assert 'route.repeat_interval_minutes' in notifications
    assert 'min(repeat' not in notifications


def test_severity_escalation_is_a_first_class_event_and_pages_immediately() -> None:
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')
    notifications = read('app/intelligence/alert_intelligence/notifications.py')
    model = read('app/models/alert_ops.py')
    assert 'previous_severity' in model
    assert 'severity_changed_at' in model
    assert "'severity_escalated'" in source
    assert "'severity_deescalated'" in source
    assert 'def _severity_escalation_due' in notifications
    assert 'and not escalation_due' in notifications


def test_resolved_workspace_is_source_state_based_not_close_only() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_history.html')
    assert "row.source_state == 'firing'" in service
    assert "row.source_state == 'resolved'" in service
    assert "('resolved', 'Resolved'" in workspace
    assert 'Verification Pending' in resolved
    assert 'Verify & Close' in resolved


def test_notification_templates_are_provider_format_aware_and_resettable() -> None:
    model = read('app/models/alert_ops.py')
    templates = read('app/intelligence/alert_intelligence/templates.py')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    ui = read('app/templates/intelligence/partials/_alert_ops_templates.html')
    assert "content_format IN ('plain_text', 'markdown', 'html')" in model
    assert "'telegram': ('plain_text', 'markdown', 'html')" in templates
    assert "'email': ('plain_text', 'html')" in templates
    assert "'microsoft_teams': ('plain_text', 'markdown')" in templates
    assert 'def _validate_safe_html' in templates
    assert 'def render_template_preview' in templates
    assert "@alert_intelligence_bp.post('/templates/test-render')" in routes
    assert "@alert_intelligence_bp.post('/templates/send-test')" in routes
    assert "@alert_intelligence_bp.post('/templates/reset')" in routes
    assert 'Rendered Preview' in ui
    assert 'Test Render' in ui
    assert 'Send Test' in ui
    assert 'Reset to System Template' in ui


def test_alert_worker_and_automation_use_kaori_durable_cases_only() -> None:
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')
    candidates = read('app/intelligence/automation_control/candidates.py')
    service = read('app/intelligence/alert_intelligence/service.py')
    assert 'reconcile_alert_cases()' not in worker
    assert 'reconcile_recommendation_alert_cases()' in worker
    assert "AlertCase.source_type == 'recommendation'" in candidates
    assert "AlertCase.source_state == 'firing'" in candidates
    assert 'list_active_alert_events' not in candidates
    assert 'raw provider snapshots' in service
    assert "'autonomous_execution_allowed': not human_controlled" in candidates


def test_verified_automation_closes_the_originating_alert_case() -> None:
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    resolver = read('app/intelligence/resolver/service.py')
    assert 'def close_case_from_automation_verification' in lifecycle
    assert "'automation_resolution'" in lifecycle
    assert "'automation_verified_resolution'" in lifecycle
    assert "(decision.evidence_json or {}).get('alert_case_id')" in resolver
    assert 'close_case_from_automation_verification(' in resolver


def test_migration_captures_alert_management_foundation_fields() -> None:
    migration = read('migrations/versions/20260822_alert_management_foundation.py')
    assert "revision = '20260822_alert_mgmt_foundation'" in migration
    assert "down_revision = '20260822_reco_alert_escalation'" in migration
    for field in ('previous_severity', 'severity_changed_at', 'acknowledgement_expires_at', 'acknowledgement_timeout_minutes', 'content_format'):
        assert field in migration
