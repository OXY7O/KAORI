from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_snapshot_dimensions_exclude_local_record_controls() -> None:
    routes = read('app/analytics/top_consumers/routes.py')
    snapshot_parameters = routes.split('def _snapshot_parameters', 1)[1].split('def _context_or_state', 1)[0]

    assert "request.args.get('cluster_id'" in snapshot_parameters
    assert "request.args.get('namespace'" in snapshot_parameters
    for local_parameter in ('resource', 'search', 'sort', 'priority', 'focus', 'page', 'per_page', 'tab'):
        assert f"request.args.get('{local_parameter}'" not in snapshot_parameters


def test_fragment_transport_is_htmx_only_and_no_store() -> None:
    routes = read('app/analytics/top_consumers/routes.py')

    assert "request.headers.get('HX-Request', '').lower() == 'true'" in routes
    assert 'return redirect(_full_page_url())' in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "response.headers['Vary'] = 'HX-Request'" in routes
    assert "response.headers['HX-Push-Url'] = _full_page_url()" in routes


def test_legacy_top_consumers_section_surface_is_removed() -> None:
    analytics_routes = read('app/analytics/routes.py')
    domain_routes = read('app/analytics/top_consumers/routes.py')
    navigation = read('app/templates/components/navigation/analytics_menu.html')

    assert 'top_consumers_section' not in analytics_routes
    assert 'def top_consumers_section' not in domain_routes
    assert 'analytics.top_consumers_section' not in navigation


def test_promql_normalizes_series_and_uses_ready_worker_capacity() -> None:
    profile = read('app/integrations/prometheus/query_profiles/kubernetes_v1.py')

    assert 'def _tc_active_worker_pods(' in profile
    assert 'max by (namespace, pod, container)' in profile
    assert "phases: str = 'Pending|Running'" in profile
    assert 'phases="Running"' in profile
    assert 'kube_node_status_condition{condition="Ready", status="true"} == 1' in profile
    assert 'kube_node_role{role=~"control-plane|master"}' in profile
    assert 'max by (namespace, persistentvolumeclaim)' in profile
    assert 'kubelet_volume_stats_capacity_bytes' in profile
    top_consumers = profile.split("'analytics.top_consumers.queries.NAMESPACE_ACTIVE_QUERY'", 1)[1].split(
        "'analytics.utilization.queries.CPU_CAPACITY'", 1
    )[0]
    assert 'kube_persistentvolumeclaim_resource_requests_storage_bytes' not in top_consumers


def test_missing_advisory_capability_does_not_become_confirmed_zero() -> None:
    evidence = read('app/analytics/top_consumers/evidence.py')

    assert 'TOP_CONSUMERS_ADVISORY_CAPABILITIES' in evidence
    assert 'if not rows and advisory_capability in advisory_missing:' in evidence
    assert 'an empty query result is not treated as confirmed zero' in evidence
    assert "advisory_capability='resource_requests_limits'" in evidence
    assert "advisory_capability='capacity_metrics'" in evidence
    assert "advisory_capability='pvc_usage'" in evidence


def test_namespace_snapshot_mismatch_is_not_projected_as_cluster_data() -> None:
    presentation = read('app/analytics/top_consumers/presentation.py')

    assert 'if selected_namespace and snapshot_namespace != selected_namespace:' in presentation
    assert "payload['snapshot_scope_mismatch'] = True" in presentation
    assert 'does not match the requested Namespace' in presentation


def test_report_uses_canonical_selection_contract() -> None:
    report = read('app/reports/export/payloads/top_consumers.py')
    contracts = read('app/analytics/top_consumers/contracts.py')
    service = read('app/analytics/top_consumers/service.py')

    assert 'class TopConsumersSelection:' in contracts
    assert 'TopConsumersSelection(' in report
    assert "sort='priority'" in report
    assert "'selected_time_range': 'current'" in report
    assert 'selection: TopConsumersSelection' in service
    assert "selected_sort='usage_percent'" not in report


def test_top_consumers_runtime_modules_remain_bounded() -> None:
    modules = (
        'contracts.py',
        'evidence.py',
        'domain.py',
        'presentation.py',
        'recommendations.py',
        'rows.py',
        'routes.py',
        'service.py',
    )
    for module in modules:
        source = read(f'app/analytics/top_consumers/{module}')
        assert len(source.splitlines()) <= 800, module

    service = read('app/analytics/top_consumers/service.py')
    rows = read('app/analytics/top_consumers/rows.py')
    assert 'def build_consumer_row(' not in service
    assert 'def build_consumer_row(spec: ConsumerRowSpec)' in rows
