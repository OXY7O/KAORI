from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_intelligence_baseline_lock_distinguishes_safe_current_state_from_feature_completion():
    readme = read('app/intelligence/README.md')
    standard = read('docs/design/components/INTELLIGENCE_WORKSPACE_STANDARD.md')
    lock = read('docs/design/KAORI_INTELLIGENCE_BASELINE_LOCK_V1.md')

    assert 'baseline-locked' in readme
    assert 'not declared feature-complete' in readme
    assert '## Baseline lock semantics' in standard
    assert '**Baseline lock, not feature-complete lock.**' in lock
    assert 'Server recommendation/evidence providers.' in lock
    assert 'HCI recommendation/evidence providers.' in lock


def test_automation_control_remains_fail_closed_while_reserved_plan_work_is_incomplete():
    routes = read('app/automation_control/routes.py')
    presentation = read('app/automation_control/presentation.py')
    default_config = read('app/config/default.py')

    mutation_gate = routes.split('def _handle_mutation(', 1)[1].split('def _handle_control_operation(', 1)[0]
    assert "current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)" in mutation_gate
    gate_position = mutation_gate.index("current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)")
    operation_position = mutation_gate.index('_handle_control_operation(')
    assert gate_position < operation_position
    assert "title='Automation Mutation Disabled'" in mutation_gate
    assert 'detail=str(exc)' not in routes
    assert "'posture': overview_state['posture']" in presentation
    assert 'Governance Only' in read('app/automation_control/overview.py')
    assert 'DOMAIN_DEFINITIONS' not in presentation
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in default_config
    governance_gate = routes.split('def _handle_governance_action(', 1)[1].split('def _handle_mutation(', 1)[0]
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in governance_gate


def test_alert_intelligence_uses_supported_multi_domain_alert_sources():
    module = read('app/alert_intelligence/service.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    assert 'load_alerts_by_source' in module
    assert 'load_alert_stream' in module
    assert 'get_active_recommendation_findings' in module
    assert "'kubernetes'" in module
    assert "'object_storage'" in module
    assert 'Alertmanager is preferred' in workspace
    assert 'Prometheus ALERTS' in workspace
    assert 'This is contextual correlation, not a claim that every finding was caused by every alert.' in workspace


def test_intelligence_baseline_lock_is_registered_in_quality_gate():
    quality_gate = read('scripts/quality_gate.sh')
    assert 'python scripts/verify_intelligence_baseline_lock.py' in quality_gate
