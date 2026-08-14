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
        'automation.decision_approved',
        'automation.decision_rejected',
        'automation.execution_started',
        'automation.execution_completed',
        'automation.execution_failed',
        'automation.verification_failed',
    ):
        assert event_type in forms
        assert event_type in service


def test_decision_governance_is_enabled_while_infrastructure_mutation_remains_gated():
    routes = read('app/automation_control/routes.py')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')

    governance = routes.split('def _handle_governance_action(', 1)[1].split('def _handle_mutation(', 1)[0]
    mutation = routes.split('def _handle_mutation(', 1)[1].split('def _handle_control_operation(', 1)[0]
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in governance
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' in mutation
    assert 'Governance Workflow Enabled' in decisions
    assert 'Promote to Decision' in decisions
    assert 'Approve Decision' in decisions
    assert 'Reject Decision' in decisions
    assert 'Approval Notification Delivery' in decisions


def test_automation_decision_notifications_are_async_and_provider_neutral():
    routes = read('app/automation_control/routes.py')
    notifications = read('app/automation_control/notifications.py')
    tasks = read('app/automation_control/tasks.py')
    channel_service = read('app/notification_channels/service.py')
    config = read('app/config/default.py')

    assert '_queue_decision_notification' in routes
    assert 'dispatch_matching_notification_event' in notifications
    assert 'dispatch_notification_event(channel_ids=channel_ids, event=event)' in channel_service
    assert "name='app.automation_control.tasks.dispatch_automation_decision_notification'" in tasks
    assert "'app.automation_control.tasks'" in config
    assert "'app.automation_control.tasks.dispatch_automation_decision_notification'" in config
    for provider_token in ('telegram', 'smtp', 'teams'):
        assert provider_token not in notifications.lower()
