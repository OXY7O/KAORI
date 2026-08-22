from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_case_supports_unknown_source_and_reversible_routing_state() -> None:
    model = read('app/models/alert_ops.py')
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    case_state = read('app/intelligence/alert_intelligence/case_state.py')

    assert "source_state IN ('firing', 'resolved', 'unknown')" in model
    assert "routing_state IN ('enabled', 'suppressed')" in model
    for field in (
        'source_state_reason',
        'source_state_changed_at',
        'routing_override_reason',
        'routing_override_note',
        'closure_reason',
    ):
        assert field in model
    assert 'mark_case_source_unknown' in lifecycle
    assert 'def mark_case_source_unknown(' in case_state
    assert 'def restore_case_source_firing(' in case_state
    assert 'def suppress_case_routing(' in case_state
    assert 'def resume_case_routing(' in case_state


def test_missing_findings_only_resolve_after_fresh_source_evidence() -> None:
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')

    assert 'fresh_keys: set[str] = set()' in source
    assert 'def _source_evidence_posture_for_finding' in source
    assert 'def _source_evidence_posture_for_state' in source
    assert 'mark_case_source_unknown(' in source
    assert 'restore_case_source_firing(' in source
    assert "return False, 'source_deleted'" in source
    assert "'source_unavailable'" in source


def test_policy_ineligible_suppresses_delivery_without_claiming_resolution() -> None:
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')
    case_state = read('app/intelligence/alert_intelligence/case_state.py')

    assert 'set_case_policy_routing_eligibility(case, eligible=False' in source
    assert "reason='policy_ineligible'" in case_state
    assert 'The source condition remains active' in case_state


def test_manual_routing_can_stop_resume_and_withdraw_without_deleting_history() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    case_state = read('app/intelligence/alert_intelligence/case_state.py')
    ui = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')

    assert "/routing/suppress'" in routes
    assert "/routing/resume'" in routes
    assert "/withdraw'" in routes
    assert 'def withdraw_manual_alert(' in case_state
    assert "case.closure_reason = 'manual_withdrawal'" in case_state
    assert 'promotion_suppressed_until_clear = True' in case_state
    assert 'Stop Routing' in ui
    assert 'Resume Routing' in ui
    assert 'Withdraw Alert' in ui
    service = read('app/intelligence/alert_intelligence/service.py')
    assert "'manual_promotion': manual_promotion" in service
    assert "'manually promoted' in str(event['summary'] or '').lower()" in service
    assert '{% if case.manual_promotion %}' in ui


def test_source_delete_is_unknown_not_resolved_and_can_be_retired() -> None:
    case_state = read('app/intelligence/alert_intelligence/case_state.py')
    cluster = read('app/kubernetes/cluster/service.py')
    object_storage = read('app/integrations/storage/object_storage/providers/minio/application/service.py')
    routes = read('app/intelligence/alert_intelligence/routes.py')

    assert 'def mark_asset_alert_cases_source_unknown(' in case_state
    assert "reason='source_deleted'" in cluster
    assert "reason='source_deleted'" in object_storage
    assert 'def retire_source_deleted_case(' in case_state
    assert "case.closure_reason = 'source_decommissioned'" in case_state
    assert "/retire-source'" in routes


def test_notification_channel_disabled_is_suppressed_while_runtime_failure_remains_failed() -> None:
    notifications = read('app/intelligence/alert_intelligence/notifications.py')

    assert "return 'channel_disabled'" in notifications
    assert "return 'channel_not_configured'" in notifications
    assert "return 'channel_not_validated'" in notifications
    assert "'delivery_state': 'suppressed'" in notifications
    assert "delivery.status = 'skipped'" in notifications
    assert "'failed'" in notifications


def test_unknown_or_operator_suppressed_cases_cannot_autonomously_execute() -> None:
    candidates = read('app/intelligence/automation_control/candidates.py')
    routing = read('app/intelligence/alert_intelligence/routing.py')

    assert "AlertCase.source_state == 'firing'" in candidates
    assert "routing_suppressed = case.routing_state == 'suppressed'" in candidates
    assert "'autonomous_execution_allowed': not human_controlled" in candidates
    assert "if case.source_state != 'firing' or case.routing_state != 'enabled':" in routing


def test_migration_adds_unknown_routing_and_manual_withdrawal_fields() -> None:
    migration = read('migrations/versions/20260822_alert_source_unknown_routing.py')

    assert "revision = '20260822_alert_source_unknown'" in migration
    assert "down_revision = '20260822_alert_mgmt_foundation'" in migration
    for field in (
        'source_state_reason',
        'source_state_changed_at',
        'routing_state',
        'routing_override_reason',
        'routing_override_note',
        'closure_reason',
        'promotion_suppressed_until_clear',
    ):
        assert field in migration
