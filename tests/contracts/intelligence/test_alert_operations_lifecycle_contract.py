from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_case_separates_source_workflow_and_delivery_state() -> None:
    model = read('app/models/alert_ops.py')
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')

    assert "source_state IN ('firing', 'resolved')" in model
    assert "workflow_state IN ('open', 'acknowledged', 'mitigating', 'verification_pending', 'closed')" in model
    assert 'AlertSilence' in model
    assert 'AlertCaseEvent' in model
    assert "case.workflow_state = 'verification_pending'" in lifecycle
    assert "case.workflow_state = 'closed'" in lifecycle


def test_operator_close_requires_resolution_steps_and_verification_evidence() -> None:
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')

    assert "raise ValueError('Resolution summary is required.')" in lifecycle
    assert "raise ValueError('At least one remediation or recovery step is required.')" in lifecycle
    assert "raise ValueError('Verification evidence is required before closure.')" in lifecycle
    assert "if case.source_state != 'resolved'" in lifecycle
    assert "case.postmortem_required = _requires_postmortem(case)" in lifecycle


def test_kaori_silence_is_time_bounded_and_separate_from_alertmanager() -> None:
    model = read('app/models/alert_ops.py')
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    notifications = read('app/intelligence/alert_intelligence/notifications.py')

    assert 'KAORI delivery silence; intentionally separate from Alertmanager silences.' in model
    assert 'duration = max(5, min(int(duration_minutes or 0), 10080))' in lifecycle
    assert 'active_delivery_silence(case, now=now)' in notifications
    assert 'silence_expired' in lifecycle


def test_alert_incident_archive_is_closed_only_and_preserves_searchable_index() -> None:
    domain = read('app/platform_operations/data_lifecycle/retention/domains/alert_incident.py')
    migration = read('migrations/versions/20260822_alert_operations_lifecycle.py')

    assert "name = 'alert_incident'" in domain
    assert "AlertCase.workflow_state == 'closed'" in domain
    assert 'AlertCase.archive_compacted_at.is_(None)' in domain
    assert 'AlertCaseEvent.query.filter_by(case_id=case.id).delete' in domain
    assert 'case.archive_compacted_at = datetime.now(UTC)' in domain
    assert "domain='alert_incident'" in migration
    assert 'archive_retention_days=730' in migration
    assert 'schedule_hour=4' in migration and 'schedule_minute=45' in migration


def test_alert_operations_permissions_split_operator_decisions_from_integration_governance() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')

    assert "@permission_required('intelligence.decisions.create')" in routes
    assert "@permission_required('integrations.manage')" in routes
    assert "@alert_intelligence_bp.post('/routing')" in routes
    assert "@alert_intelligence_bp.post('/templates')" in routes
