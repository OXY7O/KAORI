from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_evidence_coverage_contract_has_complete_partial_and_unavailable_states() -> None:
    source = read('app/analytics/workload/mapping.py')

    assert 'def metrics_coverage(' in source
    assert "'label': 'Complete'" in source
    assert "'label': 'Partial'" in source
    assert "'label': 'Unavailable'" in source
    assert "'description': f'{pod_count} of {pod_count} Pods'" in source
    assert "'description': f'{complete} of {pod_count} Pods'" in source


def test_right_sizing_is_deferred_until_evidence_is_complete() -> None:
    source = read('app/analytics/workload/mapping.py')

    assert "if metrics_label != 'Complete':" in source
    assert "return 'Defer right-sizing until metrics coverage is complete'" in source
    assert "'cpu_current': item['cpu_current_pods'] == pod_count" in source
    assert "'cpu_peak': item['cpu_peak_pods'] == pod_count" in source
    assert "'memory_current': item['memory_current_pods'] == pod_count" in source
    assert "'memory_peak': item['memory_peak_pods'] == pod_count" in source


def test_qos_is_factual_metadata_not_health_state() -> None:
    mapping_source = read('app/analytics/workload/mapping.py')
    template = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert "return {'label': 'Mixed'}" in mapping_source
    assert "return {'label': next(iter(distribution))}" in mapping_source
    assert 'table_label.metadata_label(row.qos.label' in template
    assert 'table_label.status_label(row.qos.label' not in template
