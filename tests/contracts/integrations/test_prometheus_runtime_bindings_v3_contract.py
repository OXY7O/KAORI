from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_prometheus_runtime_uses_decision_layout_and_filtered_history() -> None:
    detail = read('app/templates/prometheus/partials/_detail_runtime.html')
    runtime = read('app/templates/prometheus/partials/_runtime_panel.html')

    assert 'runtime_history_filters_enabled=true' in detail
    assert "runtime_history_endpoint='prometheus.instance_runtime_history'" in detail
    assert 'data-kaori-prometheus-runtime-layout' in runtime
    assert 'Runtime Snapshot' in runtime
    assert 'Diagnostic Evidence' in runtime
    assert 'Runtime Decision' in runtime
    assert 'Evidence Ownership' in runtime
    assert 'Endpoint Context' in runtime
    assert 'Operational Focus' in runtime
    assert 'Next Operational Action' in runtime
    assert 'workspace_summary_card' not in detail


def test_prometheus_bindings_use_kaori_table_and_native_create_dialog() -> None:
    template = read('app/templates/prometheus/partials/_detail_scope.html')

    assert 'Bindings &amp; Consumers' in template
    assert 'Bound Kubernetes Scopes' in template
    assert 'Effective Consumer Resolution' in template
    assert 'Binding Decision' in template
    assert 'table_ui.table_classes' in template
    assert 'integration_status(row.validation_status, display=\'indicator\')' in template
    assert '<dialog id="prometheus-create-binding-dialog"' in template
    assert "showModal()" in template
    assert 'm-auto w-[min(44rem,calc(100vw-2rem))]' in template


def test_prometheus_runtime_history_filters_are_server_side() -> None:
    routes = read('app/prometheus/routes.py')
    presentation = read('app/prometheus/presentation.py')

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
