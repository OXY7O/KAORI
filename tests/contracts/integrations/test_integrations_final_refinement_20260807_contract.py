from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minimum_validation_rbac_remains_modal() -> None:
    source = read('app/templates/integrations/kubernetes/partials/_minimum_validation_rbac.html')

    assert 'Minimum Validation RBAC Example' in source
    assert 'Open RBAC Examples' in source
    assert 'x-teleport="body"' in source
    assert 'role="dialog"' in source
    assert 'aria-modal="true"' in source
    assert 'data-kaori-rbac-modal-tabs' in source
    assert 'data-kaori-rbac-tabs-integrated' in source
    assert 'mb-4 rounded-xl border border-outline-subtle bg-surface-card' not in source
    assert 'id="minimum-rbac-panel-baseline"' in source
    assert 'id="minimum-rbac-panel-secret"' in source
    assert "activeTab: 'baseline'" in source
    assert "activeTab === 'secret'" in source
    assert 'components/workspace_tabs.html' in source
    assert 'max-w-5xl' in source
    assert 'data-kaori-rbac-modal-tab-panels' in source
    assert 'max-h-[26rem]' in source
    assert 'max-h-[22rem]' in source
    assert 'xl:grid-cols-2' not in source
    assert '<details' not in source


def test_kubernetes_runtime_health_uses_latest_decision_workspace() -> None:
    source = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')

    assert 'Runtime Health & Diagnostics' in source
    assert 'data-kaori-runtime-workspace-v8' in source
    assert 'Runtime Decision' in source
    assert 'data-kaori-runtime-decision-summary' in source
    assert 'Runtime Posture' in source
    assert 'Primary Finding' in source
    assert 'Diagnostic Evidence' in source
    assert 'runtime_state.message' not in source
    assert 'Persisted Runtime Refresh evidence' in source


def test_integration_scope_pagination_uses_title_case_item_label() -> None:
    coverage = read('app/templates/components/integration_coverage_content.html')
    provider_registry = read('app/templates/integrations/components/_provider_registry.html')

    assert "item_label='Assets'" in coverage
    assert "item_label='Connections'" in provider_registry


def test_prometheus_validation_keeps_compact_contract_and_modal_detail() -> None:
    source = read('app/templates/prometheus/partials/_detail_validation_content.html')
    registry = read('app/templates/prometheus/partials/_capability_registry.html')

    assert 'import "integrations/components/_record_detail_modal.html" as record_detail_modal' in registry
    assert 'Prometheus Core Validation' in source
    assert 'record_actions.view_more(' in registry
    assert 'provider_capability_detail.content(' in registry
    assert 'provider_capability_detail.content(' in registry
    assert 'Provider API Probe' in registry
    assert 'Hide Details' not in source
    assert 'x-show="open"' not in source


def test_alertmanager_capability_matrix_uses_modal_detail() -> None:
    source = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    registry = read('app/templates/alertmanager/partials/_capability_registry.html')
    bindings = read('app/templates/alertmanager/partials/_binding_registry.html')

    assert 'import "integrations/components/_record_detail_modal.html" as record_detail_modal' in registry
    assert 'Alertmanager Core Validation' in source
    assert 'Full Validation owns provider compatibility and core API evidence only.' in source
    assert 'Consumer Binding Registry' in bindings
    assert 'record_actions.view_more(' in registry
    assert 'provider_capability_detail.content(' in registry
    assert 'Provider API Probe' in registry
    assert 'Hide Details' not in source
    assert 'x-show="open"' not in source

