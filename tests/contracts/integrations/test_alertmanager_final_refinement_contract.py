from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERT_REGISTRY = (
    ROOT
    / 'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html'
)
ALERT_ROUTES = ROOT / 'app/integrations/observability/alert_source/providers/alertmanager/application/routes.py'


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_alertmanager_validation_matches_kubernetes_capability_matrix_and_registry_loading():
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html'
    )
    registry = ALERT_REGISTRY.read_text()
    routes = ALERT_ROUTES.read_text()
    assert 'Alertmanager Full Validation' in content
    assert 'Alertmanager Provider Readiness' in content
    assert (
        'Full Validation owns core APIs; bindings own consumer evidence; Runtime Refresh owns live health.' in content
    )
    assert 'data-kaori-provider-capability-matrix' in content
    assert 'capability_readiness.render(' in content
    assert (
        'include "integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html"'
        in content
    )
    assert 'Validation Decision' not in content
    assert 'alertmanager-capability-loading' in registry
    assert 'active=validation_job and validation_job.is_active' not in registry
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
    assert 'provider_capability_detail.content(' in registry
    assert 'record_actions.view_more(' in registry
    assert 'Alertmanager Capability Evidence' in registry
    assert 'Provider API Probe' in registry
    assert 'size="standard"' in registry or "size='standard'" in registry
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
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html'
    )
    assert 'data-kaori-provider-runtime-kubernetes-pattern' in content
    assert 'integrations/components/_runtime_decision.html' in content
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
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )
    assert 'data-kaori-alertmanager-binding-decision-horizontal' in content
    assert 'data-kaori-alertmanager-consumer-resolution-full-width' in content
    assert 'data-kaori-alertmanager-lifecycle-horizontal' in content
    assert 'Connection Lifecycle' in content
    assert 'Delete Connection' in content
    assert 'bg-status-critical px-4' not in content
    assert 'xl:sticky' not in content
    assert 'min-w-[76rem]' not in content
    assert 'data-kaori-bound-scopes-full-width' in registry
    assert 'table-fixed' in registry
    assert 'table_ui.action_classes(true)' in registry


def test_alertmanager_capability_pagination_precomputes_hx_urls() -> None:
    registry = ALERT_REGISTRY.read_text(encoding='utf-8')

    assert 'previous_registry_url = url_for(registry_endpoint' in registry
    assert 'next_registry_url = url_for(registry_endpoint' in registry
    assert 'hx-get="{{ previous_registry_url }}"' in registry
    assert 'hx-get="{{ next_registry_url }}"' in registry
