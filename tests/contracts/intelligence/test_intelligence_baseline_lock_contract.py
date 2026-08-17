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


def test_automation_control_keeps_infrastructure_execution_fail_closed_without_blocking_governance():
    routes = read('app/automation_control/routes.py')
    presentation = read('app/automation_control/presentation.py')
    default_config = read('app/config/default.py')
    enablement = read('app/common/automation_execution.py')
    workflow = read('app/intelligence/workflow.py')
    resolver_tasks = read('app/resolver/tasks.py')

    governance = routes.split('def _handle_governance_mutation(', 1)[1].split('def _handle_execution_action(', 1)[0]
    execution = routes.split('def _handle_execution_action(', 1)[1].split('def _handle_control_operation(', 1)[0]
    assert 'execution_enabled()' not in governance
    assert 'execution_enabled()' in execution
    assert "title='Infrastructure Execution Disabled'" in execution
    assert "AUTOMATION_EXECUTION_ENABLED = _env_bool('AUTOMATION_EXECUTION_ENABLED', False)" in default_config
    assert 'assert_execution_enabled()' in workflow
    assert 'assert_execution_enabled()' in resolver_tasks
    assert 'AUTOMATION_EXECUTION_ENABLED' in enablement
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in routes + presentation + default_config
    assert 'detail=str(exc)' not in routes
    assert "'posture': overview_state['posture']" in presentation
    assert 'Governance Only' in read('app/automation_control/overview.py')
    assert 'DOMAIN_DEFINITIONS' not in presentation


def test_alert_intelligence_uses_supported_multi_domain_alert_sources():
    module = read('app/alert_intelligence/service.py')
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')
    correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')

    assert 'load_alerts_by_source' in module
    assert 'load_alert_stream' in module
    assert 'get_active_recommendation_findings' in module
    assert "'kubernetes'" in module
    assert "'object_storage'" in module
    assert 'Alertmanager is preferred' in alerts
    assert 'Metrics Source ALERTS' in alerts
    assert 'This is contextual correlation, not a claim that every finding was caused by every alert.' in correlation


def test_intelligence_baseline_lock_is_registered_in_quality_gate():
    quality_gate = read('scripts/quality_gate.sh')
    assert 'python scripts/verify_intelligence_baseline_lock.py' in quality_gate
