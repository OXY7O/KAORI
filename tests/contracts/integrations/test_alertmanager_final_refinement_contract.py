from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERT_REGISTRY = ROOT / 'app/templates/alertmanager/partials/_capability_registry.html'
ALERT_ROUTES = ROOT / 'app/alertmanager/routes.py'


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_alertmanager_validation_matches_kubernetes_capability_matrix_and_registry_loading():
    content = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    registry = ALERT_REGISTRY.read_text()
    routes = ALERT_ROUTES.read_text()
    assert 'Alertmanager Capability Readiness' in content
    assert 'data-kaori-provider-capability-matrix' in content
    assert "capability_readiness.render(" in content
    assert "include 'alertmanager/partials/_capability_registry.html'" in content
    assert 'Validation Decision' not in content
    assert 'alertmanager-capability-loading' in registry
    assert 'hx-indicator="#{{ loading_id }}"' in registry
    assert 'data-kaori-server-filtered-registry' in registry
    assert 'components/pagination.html' in registry
    assert 'table-fixed' in registry
    assert 'x-model' not in registry
    assert "@alertmanager_bp.get('/instances/<int:instance_id>/validation/capabilities')" in routes
    assert 'def instance_capability_registry' in routes

def test_alertmanager_validation_modal_matches_kubernetes_capability_evidence_concept():
    registry = ALERT_REGISTRY.read_text()
    shared = read('app/templates/integrations/components/_provider_capability_detail.html')
    actions = read('app/templates/integrations/components/_record_actions.html')
    assert "provider_capability_detail.content(" in registry
    assert "record_actions.view_more(" in registry
    assert "'Alertmanager Capability Evidence'" in registry
    assert "'Runnable API Request'" in registry
    assert "size='standard'" in registry
    for token in (
        'Capability Contract',
        'Validation Evidence',
        'Success Criteria',
        'Operational Impact',
        'Recommended Action',
        'Technical Verification',
        'Evidence Boundary',
    ):
        assert token in shared
    assert '{% import "components/table.html" as table_ui %}' in actions
    assert '{{ table_ui.action_classes() }}' in actions
    assert 'data-lucide="chevron-right"' in actions
    assert 'panel-top-open' not in actions


def test_alertmanager_runtime_matches_kubernetes_full_width_runtime_pattern():
    content = read('app/templates/alertmanager/partials/_runtime_panel.html')
    assert 'data-kaori-provider-runtime-kubernetes-pattern' in content
    assert "integrations/components/_runtime_decision.html" in content
    assert 'runtime_decision.render(' in content
    assert 'data-kaori-alertmanager-runtime-evidence' in content
    assert 'Runtime Evidence' in content
    assert 'step.summary' in content
    assert 'step.detail' not in content
    assert 'step.recommendation' not in content
    assert 'lg:sticky' not in content
    assert 'xl:sticky' not in content
    assert 'grid-cols-[minmax(0,1fr)_25rem]' not in content

def test_alertmanager_binding_workspace_is_full_width_and_lifecycle_action_is_secondary():
    content = read('app/templates/alertmanager/partials/_detail_scope.html')
    assert 'data-kaori-alertmanager-binding-decision-horizontal' in content
    assert 'data-kaori-alertmanager-consumer-resolution-full-width' in content
    assert 'data-kaori-alertmanager-lifecycle-horizontal' in content
    assert 'Connection Lifecycle' in content
    assert 'Delete Connection' in content
    assert 'bg-status-critical px-4' not in content
    assert 'xl:sticky' not in content
    assert 'min-w-[76rem]' not in content
    assert 'table-fixed' in content
    assert 'table_ui.action_classes(true)' in content
