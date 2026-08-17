from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_snapshot_variants_exclude_presentation_state() -> None:
    routes = read('app/analytics/kubernetes/workload/routes.py')

    snapshot_block = routes[routes.index('def _snapshot_parameters') : routes.index('def _selected_tab')]
    assert "parameters['time_range']" in snapshot_block
    assert "parameters['cluster_id']" in snapshot_block
    for token in ('namespace', 'tab', 'search', 'quota_page', 'workload_page', 'per_page'):
        assert f"parameters['{token}']" not in snapshot_block


def test_workload_fragments_require_htmx_and_disable_cache() -> None:
    routes = read('app/analytics/kubernetes/workload/routes.py')

    assert "request.headers.get('HX-Request', '').lower() == 'true'" in routes
    assert "return redirect(_full_workload_url('quotas'))" in routes
    assert "return redirect(_full_workload_url('mapping'))" in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "response.headers['Vary'] = 'HX-Request'" in routes
    assert "response.headers['HX-Push-Url']" in routes


def test_active_deep_link_renders_directly_and_inactive_tabs_are_lazy() -> None:
    index = read('app/templates/analytics/kubernetes/workload/index.html')

    assert "{% if active_tab == 'quotas' %}" in index
    assert "{% if active_tab == 'mapping' %}" in index
    assert index.count('kaori:analytics-tab-activated once') == 2
    assert 'hx-swap="outerHTML"' in index


def test_promql_is_active_pod_scoped_and_deduplicates_scrape_series() -> None:
    profile = read('app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py')
    workload_block = profile[profile.index("'analytics.workload.queries.NAMESPACE_ACTIVE_QUERY'") :]

    assert 'phase=~"Pending|Running"' in workload_block
    assert 'max by (namespace, pod, container)' in workload_block
    assert 'max by (namespace, pod)' in workload_block
    assert 'kube_pod_info{namespace!=""}' not in workload_block


def test_resource_quota_keeps_object_identity_and_independent_pressure() -> None:
    profile = read('app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py')
    quota = read('app/analytics/kubernetes/workload/quota.py')

    assert 'max by (namespace, resourcequota, resource, type)' in profile
    assert "quota_name = metric.get('resourcequota')" in quota
    assert 'values.setdefault(namespace, {}).setdefault(quota_name, {})' in quota
    assert "'quota_pressure_object': data['pressure_object']" in quota
    assert 'runtime_demand_object' in quota


def test_service_is_orchestration_only_and_domain_ownership_is_split() -> None:
    service = read('app/analytics/kubernetes/workload/service.py')

    assert 'from app.analytics.kubernetes.workload.quota import' in service
    assert 'from app.analytics.kubernetes.workload.mapping import' in service
    assert 'from app.analytics.kubernetes.workload.domain import' in service
    assert 'def get_all_namespace_options(' not in service
    assert 'def get_metrics_coverage(' not in service
    assert 'def get_workload_recommendation(' not in service
    assert len(service.splitlines()) < 500


def test_materialization_does_not_apply_namespace_filters_or_pagination() -> None:
    service = read('app/analytics/kubernetes/workload/service.py')
    presenter = read('app/analytics/kubernetes/workload/presentation.py')
    report = read('app/reports/export/payloads/workload.py')

    materialize = service[
        service.index('def _materialize_workload_context') : service.index('def _empty_materialized_context')
    ]
    assert 'get_query_value' not in materialize
    assert 'filter_' not in materialize
    assert 'paginate_rows' not in materialize
    assert 'get_all_namespace_options' not in report
    assert 'paginate_rows_with_options' in presenter
    assert "name='namespace'" in presenter


def test_unknown_and_limited_evidence_are_first_class_states() -> None:
    domain = read('app/analytics/kubernetes/workload/domain.py')

    assert "'value': 'Unknown'" in domain
    assert "'value': 'Limited Evidence'" in domain
    assert "'value': 'Healthy'" in domain
    assert 'No Critical Governance Findings Detected' not in domain
