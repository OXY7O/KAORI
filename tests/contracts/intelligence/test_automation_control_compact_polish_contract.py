from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_control_compact_navigation_is_present_in_every_workspace():
    components = read('app/templates/intelligence/partials/automation_control/_components.html')
    assert 'macro workspace_nav' in components
    assert 'macro record_details' in components
    assert 'border-outline-subtle' in components
    assert 'group-open:rotate-180' in components

    for name in ('_overview.html', '_runbooks.html', '_decisions.html', '_operations.html', '_readiness.html'):
        template = read(f'app/templates/intelligence/partials/automation_control/{name}')
        assert 'automation_ui.workspace_nav' in template

    for name in ('_runbooks.html', '_decisions.html', '_operations.html', '_readiness.html'):
        template = read(f'app/templates/intelligence/partials/automation_control/{name}')
        assert 'automation_ui.record_details' in template


def test_rule_catalog_list_copy_is_compact_but_rule_detail_remains_available():
    service = read('app/intelligence/service.py')
    records = read('app/templates/intelligence/partials/_catalog_records.html')

    assert "item['table_summary'] = _truncate_words(item.get('summary'), limit=16)" in service
    assert 'Ready in the current KAORI boundary.' in records
    assert 'Enriched from an upstream signal.' in records
    assert 'Cataloged only; enabled outside this boundary.' in records
    assert 'catalog_rule_details' in records
    assert 'View Rule' in records


def test_visual_compaction_does_not_remove_runbook_or_binding_operations():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    for token in (
        'activate_automation_system_runbook',
        'create_automation_binding',
        'update_automation_binding_status',
        'Activate System Runbook',
        'Create Binding',
        'Disable Binding',
        'Enable Binding',
        'csrf_token',
    ):
        assert token in runbooks


def test_visual_compaction_does_not_remove_candidate_decision_or_execution_operations():
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')

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

    for token in (
        'update_automation_deployment_policy',
        'update_automation_operational_control',
        'Global Kill Switch',
        'Maintenance Mode',
        'Deployment Policies',
        'Execution Journal',
        'Dead-Letter Review',
        'csrf_token',
    ):
        assert token in operations


def test_visual_compaction_does_not_remove_readiness_controls():
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    for token in (
        'record_automation_readiness',
        'advance_automation_readiness',
        'target_stage',
        'Production Enablement Gate',
        'Controlled Rollout Sequence',
        'Readiness Evidence Contract',
        'Readiness Records',
        'csrf_token',
    ):
        assert token in readiness


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
