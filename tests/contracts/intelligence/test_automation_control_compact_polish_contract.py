from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_control_summary_matches_alert_operations_snapshot_language():
    main = read('app/templates/intelligence/automation_control.html')
    assert 'Automation Control Summary' in main
    assert 'intelligence_ui.posture_panel' in main
    assert 'intelligence_ui.posture_metric' in main
    for label in ('Decision Candidates', 'Awaiting Approval', 'Active Executions', 'Execution Failures'):
        assert label in main
    assert 'resource_detail_modal.host' in main


def test_runbook_workspace_is_table_first_and_binding_configuration_is_modal():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    routes = read('app/intelligence/automation_control/routes.py')
    modal = read('app/templates/intelligence/partials/automation_control/_binding_configuration_modal.html')

    assert 'Runbook &amp; Binding Snapshot' in runbooks
    for registry in (
        'automation-runbook-catalog-registry',
        'automation-runbook-library-registry',
        'automation-bindings-registry',
    ):
        assert registry in runbooks
    assert runbooks.count('table_registry.filter_form') >= 3
    assert runbooks.count('table_registry.footer') >= 3
    assert 'detail_row.static_detail_row' in runbooks
    assert 'binding_configuration_modal' in runbooks
    assert "@automation_control_bp.get('/automation-control/modals/binding')" in routes
    assert 'create_automation_binding' in modal
    assert 'csrf_token' in modal


def test_decision_workspace_uses_three_canonical_registries_without_removing_actions():
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    for registry in (
        'automation-candidate-registry',
        'automation-decision-registry',
        'automation-decision-delivery-registry',
    ):
        assert registry in decisions
    assert decisions.count('table_registry.filter_form') >= 3
    assert decisions.count('table_registry.footer') >= 3
    for token in (
        'promote_automation_candidate',
        'dismiss_automation_candidate',
        'approve_automation_decision',
        'reject_automation_decision',
        'execute_automation_decision',
        'Maker-Checker Required',
        'csrf_token',
    ):
        assert token in decisions


def test_execution_workspace_moves_forms_to_modal_but_keeps_runtime_controls():
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    modal = read('app/templates/intelligence/partials/automation_control/_execution_configuration_modal.html')
    routes = read('app/intelligence/automation_control/routes.py')

    assert 'Execution Posture Snapshot' in operations
    assert 'execution_configuration_modal' in operations
    for registry in ('automation-policy-registry', 'automation-journal-registry', 'automation-dead-letter-registry'):
        assert registry in operations
    assert 'update_automation_deployment_policy' in modal
    assert 'update_automation_operational_control' in modal
    for token in ('Global Kill Switch', 'Maintenance Mode', 'concurrency_limit', 'rate_limit_per_minute', 'csrf_token'):
        assert token in modal
    assert "@automation_control_bp.get('/automation-control/modals/execution-configuration')" in routes


def test_readiness_workspace_moves_evidence_form_to_modal_and_keeps_stage_control():
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    modal = read('app/templates/intelligence/partials/automation_control/_readiness_configuration_modal.html')
    routes = read('app/intelligence/automation_control/routes.py')

    assert 'Production Enablement Gate' in readiness
    assert 'automation-readiness-registry' in readiness
    assert 'table_registry.filter_form' in readiness
    assert 'table_registry.footer' in readiness
    assert 'advance_automation_readiness' in readiness
    assert 'target_stage' in readiness
    assert 'readiness_configuration_modal' in readiness
    assert 'record_automation_readiness' in modal
    assert 'required_checks' in modal
    assert 'csrf_token' in modal
    assert "@automation_control_bp.get('/automation-control/modals/readiness')" in routes


def test_permission_and_fail_closed_execution_boundaries_are_unchanged():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    routes = read('app/intelligence/automation_control/routes.py')

    assert "current_user.has_permission('knowledge.runbooks.manage')" in runbooks
    assert "current_user.has_permission('knowledge.runbooks.publish')" in runbooks
    assert "current_user.has_permission('intelligence.decisions.create')" in decisions
    assert "current_user.has_permission('intelligence.decisions.approve')" in decisions
    assert "current_user.has_permission('intelligence.decisions.execute')" in decisions
    assert "current_user.has_permission('intelligence.decisions.execute')" in operations
    assert "current_user.has_permission('intelligence.decisions.execute')" in readiness

    governance = routes.split('def _handle_governance_mutation(', 1)[1].split('def _handle_execution_action(', 1)[0]
    execution = routes.split('def _handle_execution_action(', 1)[1].split('def _handle_control_operation(', 1)[0]
    assert 'execution_enabled()' not in governance
    assert 'execution_enabled()' in execution
