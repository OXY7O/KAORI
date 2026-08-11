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

    mutation_gate = routes.split('def _handle_mutation(', 1)[1].split('def _actor_user_id(', 1)[0]
    assert "current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)" in mutation_gate
    gate_position = mutation_gate.index("current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)")
    operation_position = mutation_gate.index('operation()')
    assert gate_position < operation_position
    assert "title='Automation Control Reserved Plan'" in mutation_gate
    assert 'detail=str(exc)' not in routes
    assert "'posture': {'label': 'Reserved Plan', 'tone': 'unknown'}" in presentation
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in default_config


def test_alert_intelligence_keeps_unimplemented_provider_paths_reserved():
    service = read('app/intelligence/service.py')
    payload = service.split('def get_alert_intelligence_payload()', 1)[1]

    assert "'title': 'Server Signal Enrichment'" in payload
    assert "'title': 'HCI Signal Enrichment'" in payload
    assert payload.count("'status': 'Reserved Plan'") >= 3
    assert "'output': 'Reserved decision candidate'" in payload
    assert "'Automated mutation while control gates remain disabled'" in payload


def test_intelligence_baseline_lock_is_registered_in_quality_gate():
    quality_gate = read('scripts/quality_gate.sh')
    assert 'python scripts/verify_intelligence_baseline_lock.py' in quality_gate
