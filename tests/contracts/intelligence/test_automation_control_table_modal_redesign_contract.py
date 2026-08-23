from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_multi_registry_presentation_has_independent_filters_and_pagination():
    registries = read('app/intelligence/automation_control/workspace_registries.py')
    for token in (
        'catalog_pagination',
        'runbook_pagination',
        'binding_pagination',
        'candidate_pagination',
        'decision_pagination',
        'delivery_pagination',
        'policy_pagination',
        'journal_pagination',
        'dead_pagination',
        'readiness_pagination',
    ):
        assert token in registries
    for token in (
        'catalog_q',
        'runbook_q',
        'binding_q',
        'candidate_q',
        'decision_q',
        'delivery_q',
        'policy_q',
        'journal_q',
        'dead_q',
        'readiness_q',
    ):
        assert token in registries


def test_configuration_modal_routes_use_existing_permission_boundaries():
    routes = read('app/intelligence/automation_control/routes.py')
    assert "@permission_required('knowledge.runbooks.manage')\ndef binding_configuration_modal" in routes
    assert "@permission_required('intelligence.decisions.execute')\ndef execution_configuration_modal" in routes
    assert "@permission_required('intelligence.decisions.execute')\ndef readiness_configuration_modal" in routes


def test_simplification_keeps_every_primary_mutation_endpoint_reachable_from_ui():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    binding_modal = read('app/templates/intelligence/partials/automation_control/_binding_configuration_modal.html')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    execution_modal = read('app/templates/intelligence/partials/automation_control/_execution_configuration_modal.html')
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    readiness_modal = read('app/templates/intelligence/partials/automation_control/_readiness_configuration_modal.html')

    assert 'activate_automation_system_runbook' in runbooks
    assert 'update_automation_binding_status' in runbooks
    assert 'create_automation_binding' in binding_modal
    for token in (
        'promote_automation_candidate',
        'dismiss_automation_candidate',
        'approve_automation_decision',
        'reject_automation_decision',
        'execute_automation_decision',
    ):
        assert token in decisions
    assert 'update_automation_deployment_policy' in execution_modal
    assert 'update_automation_operational_control' in execution_modal
    assert 'record_automation_readiness' in readiness_modal
    assert 'advance_automation_readiness' in readiness


def test_tables_use_kaori_registry_standard_and_static_expandable_rows_for_long_detail():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')

    combined = '\n'.join((runbooks, decisions, operations, readiness))
    assert combined.count('table_registry.filter_form') >= 10
    assert combined.count('table_registry.footer') >= 10
    assert combined.count('loading_bar.render') >= 10
    assert 'detail_row.static_detail_row' in runbooks
    assert 'detail_row.static_detail_row' in decisions
    assert 'detail_row.static_detail_row' in operations
    assert 'detail_row.static_detail_row' in readiness


def test_non_overview_workspaces_share_one_padded_canvas_and_do_not_own_outer_spacing():
    page = read('app/templates/intelligence/automation_control.html')
    assert 'data-automation-control-workspace-canvas' in page
    assert "payload.workspace != 'overview'" in page
    assert 'space-y-6 bg-surface-page p-4 sm:p-5' in page

    for path in (
        'app/templates/intelligence/partials/automation_control/_runbooks.html',
        'app/templates/intelligence/partials/automation_control/_decisions.html',
        'app/templates/intelligence/partials/automation_control/_operations.html',
        'app/templates/intelligence/partials/automation_control/_readiness.html',
    ):
        template = read(path)
        assert '<div class="space-y-5">' not in template
