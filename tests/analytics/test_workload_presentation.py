from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_domain_modules_emit_semantic_payloads_without_css_classes() -> None:
    source = '\n'.join(
        read(path)
        for path in (
            'app/analytics/kubernetes/workload/domain.py',
            'app/analytics/kubernetes/workload/quota.py',
            'app/analytics/kubernetes/workload/mapping.py',
        )
    )

    assert "'tone': 'critical'" in source
    assert "'tone': 'warning'" in source
    assert "'tone': 'normal'" in source
    assert "'tone': 'unknown'" in source
    assert "'class': 'bg-" not in source


def test_configured_zero_quota_key_is_not_classified_as_missing() -> None:
    source = read('app/analytics/kubernetes/workload/quota.py')

    assert 'configured_keys = {key for values in hard_objects.values() for key in values}' in source
    assert 'missing_keys = [key for key in REQUIRED_QUOTA_KEYS if key not in configured_keys]' in source
    assert 'if not hard_values.get(key, 0)' not in source


def test_workload_runtime_terms_are_factual_and_composite_efficiency_is_removed() -> None:
    service = read('app/analytics/kubernetes/workload/service.py')
    mapping = read('app/templates/analytics/kubernetes/workload/partials/_workload_mapping_section.html')
    query_profile = read('app/integrations/metrics/query_profiles/kubernetes_v1.py')

    assert 'WORKLOAD_CPU_CURRENT_QUERY' in service
    assert 'WORKLOAD_MEMORY_CURRENT_QUERY' in service
    assert 'WORKLOAD_CPU_AVG_QUERY' not in service
    assert 'WORKLOAD_MEMORY_AVG_QUERY' not in service
    assert 'analytics.workload.queries.WORKLOAD_CPU_CURRENT_QUERY' in query_profile
    assert 'analytics.workload.queries.WORKLOAD_MEMORY_CURRENT_QUERY' in query_profile
    assert 'Average Usage' not in mapping
    assert 'Current Usage' in mapping
    assert 'Selected-Window Pod Peak Sum' in mapping
    assert 'upper-bound signal' in mapping
    assert 'Efficiency' not in mapping
    assert 'cpu_request_utilization_display' in mapping
    assert 'memory_request_utilization_display' in mapping


def test_workload_snapshot_separates_cpu_limit_policy_from_memory_limit_gaps() -> None:
    workload = read('app/analytics/kubernetes/workload/service.py')
    overview = read('app/analytics/kubernetes/overview/service.py')
    schema = read('app/analytics/kubernetes/overview/schema.py')
    template = read('app/templates/analytics/kubernetes/overview/partials/_workload_snapshot.html')

    for source in (workload, overview, schema, template):
        assert 'missing_cpu_limits' not in source
        assert 'missing_memory_limits' not in source

    assert "'cpu_limits_unset': 0" in workload
    assert "'memory_limits_missing': 0" in workload
    assert "counters['cpu_limits_unset']" in workload
    assert "counters['memory_limits_missing']" in workload
    assert 'CPU Limits Unset' in template
    assert 'Memory Limit Gaps' in template
    assert 'factual configuration' in template.lower()
