from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_evidence_coverage_contract_has_complete_partial_and_unavailable_states() -> None:
    source = read('app/analytics/workload/service.py')

    assert 'def get_metrics_coverage(' in source
    assert "'label': 'Complete'" in source
    assert "'label': 'Partial'" in source
    assert "'label': 'Unavailable'" in source
    assert "'description': f'{pod_count} of {pod_count} Pods'" in source
    assert "'description': f'{complete_observed} of {pod_count} Pods'" in source


def test_right_sizing_is_deferred_until_evidence_is_complete() -> None:
    source = read('app/analytics/workload/service.py')

    assert "if metrics_coverage != 'Complete':" in source
    assert "return 'Defer right-sizing until metrics coverage is complete'" in source
    assert "complete_metrics = metrics_coverage['label'] == 'Complete'" in source
    assert "cpu_current_available = (" in source
    assert "cpu_peak_available = (" in source
    assert "memory_current_available = (" in source
    assert "memory_peak_available = (" in source


def test_qos_is_factual_metadata_not_health_state() -> None:
    service = read('app/analytics/workload/service.py')
    template = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert "return {'label': 'Mixed'}" in service
    assert "return {'label': next(iter(qos_distribution.keys()))}" in service
    assert 'table_label.metadata_label(row.qos.label' in template
    assert 'table_label.status_label(row.qos.label' not in template
