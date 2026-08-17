from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_metrics_source_runtime_matches_kubernetes_layout_and_filtered_history() -> None:
    detail = read('app/templates/integrations/observability/metrics_source/partials/_detail_runtime.html')
    runtime = read('app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html')

    assert 'runtime_history_filters_enabled=true' in detail
    assert 'runtime_history_endpoint="metrics.instance_runtime_history"' in detail
    assert 'data-kaori-provider-runtime-kubernetes-pattern' in runtime
    assert 'integrations/components/_runtime_decision.html' in runtime
    assert 'runtime_decision.render(' in runtime
    assert 'Runtime Evidence' in runtime
    assert 'data-kaori-metrics-source-runtime-evidence' in runtime
    assert 'step.summary' in runtime
    assert 'step.detail' not in runtime
    assert 'step.recommendation' not in runtime
    assert 'lg:sticky' not in runtime
    assert 'xl:sticky' not in runtime
    assert 'workspace_summary_card' not in detail


def test_metrics_bindings_use_kaori_table_and_native_create_dialog() -> None:
    template = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    registry = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')

    assert 'Bindings &amp; Consumers' in template
    assert 'Consumer Bindings' in template
    assert 'Effective Consumer Resolution' in template
    assert 'Binding Decision' in template
    assert 'table_ui.table_classes' in registry
    assert "integration_status(row.validation_status, display='indicator')" in registry
    assert 'observability_binding_modal.render("metrics-source-create-binding-dialog"' in template
    assert 'data-kaori-dialog-open' in template
    assert 'data-dialog-target="metrics-source-create-binding-dialog"' in template
    assert '<dialog id="{{ dialog_id }}"' in modal
    assert 'm-auto w-[min(46rem,calc(100vw-2rem))]' in modal


def test_metrics_source_runtime_history_filters_are_server_side() -> None:
    routes = read('app/metrics_sources/routes.py')
    presentation = read('app/metrics_sources/presentation.py')

    for token in ['history_trigger', 'history_health', 'history_readiness']:
        assert token in routes
        assert token in presentation
    assert 'trigger_type=history_trigger' in routes
    assert 'health_status=history_health' in routes
    assert 'readiness=history_readiness' in routes


def test_runtime_history_presentation_exposes_posture_counts() -> None:
    presentation = read('app/integrations/runtime/presentation.py')

    assert "posture_counts = {'ready': 0, 'attention': 0, 'blocked': 0, 'not_observed': 0}" in presentation
    assert "'posture_counts': posture_counts" in presentation
