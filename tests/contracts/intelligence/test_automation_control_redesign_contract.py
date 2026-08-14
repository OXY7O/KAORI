from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_overview_is_operational_control_cockpit_not_foundation_map():
    overview = read('app/templates/intelligence/partials/automation_control/_overview.html')
    presentation = read('app/automation_control/presentation.py')
    posture = read('app/automation_control/overview.py')

    for label in (
        'Decision & Execution Pipeline',
        'Automation Guardrails',
        'Recent Decision Activity',
        'Execution Activity',
    ):
        assert label in overview
    assert 'Foundation Map' not in overview
    assert 'DOMAIN_DEFINITIONS' not in presentation
    assert 'Governance Only' in posture
    assert "action_key = 'kubernetes.deployment.restart'" in posture


def test_decision_and_execution_ownership_are_separate():
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    presentation = read('app/automation_control/presentation.py')

    assert 'Decision Contract' in decisions
    assert 'Candidate Review Queue' in decisions
    assert 'Persisted Decisions' in decisions
    assert 'Execution Journal' not in decisions

    assert 'Execution Posture' in operations
    assert 'Execution Journal' in operations
    assert 'Dead-Letter Review' in operations
    assert "('operations', 'Execution Control', 'server-cog')" in presentation


def test_production_readiness_separates_enablement_gates():
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    for label in (
        'Production Enablement Gate',
        'Mutation Gate',
        'Resolver Registry',
        'Active Deployment Policies',
        'Readiness Evidence',
        'Notification Delivery',
        'Controlled Rollout Sequence',
    ):
        assert label in readiness


def test_notification_channels_can_be_reserved_for_automation_lifecycle_events():
    forms = read('app/notification_channels/forms.py')
    service = read('app/notification_channels/service.py')
    for event_type in (
        'automation.approval_required',
        'automation.execution_started',
        'automation.execution_completed',
        'automation.execution_failed',
        'automation.verification_failed',
    ):
        assert event_type in forms
        assert event_type in service
