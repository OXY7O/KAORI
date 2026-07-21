from pathlib import Path


def test_prometheus_full_validation_refreshes_binding_evidence() -> None:
    tasks = Path('app/integrations/validation/tasks.py').read_text(encoding='utf-8')
    service = Path('app/prometheus/service.py').read_text(encoding='utf-8')
    coverage = Path('app/integrations/coverage.py').read_text(encoding='utf-8')
    assert 'binding_summary = _refresh_prometheus_bindings(instance)' in tasks
    assert 'validate_prometheus_binding(' in tasks
    for signal in ('kube_node_info', 'kube_namespace_status_phase', 'kube_pod_info'):
        assert signal in service
    assert 'matched_signal' in service
    assert 'Provider evidence changed after the last scope validation.' in coverage


def test_coverage_rows_show_status_only_and_consistent_scope_identity() -> None:
    template = Path('app/templates/components/integration_coverage_content.html').read_text(encoding='utf-8')
    assert 'row.coverage_detail' not in template
    assert 'Managed Kubernetes cluster' in template
    assert 'Managed Kubernetes cluster · {{ row.scope_key }}' not in template
    assert 'title="{{ row.scope_key }}"' not in template
