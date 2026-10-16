from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_kubernetes_analytics_copy_refinement_is_concise_and_domain_specific() -> None:
    overview = read('app/templates/kubernetes/analytics/overview/partials/_hero.html')
    capacity = read('app/kubernetes/analytics/capacity/routes.py')
    storage = read('app/kubernetes/analytics/storage/routes.py')
    workload = read('app/kubernetes/analytics/workload/routes.py')
    forecast = read('app/kubernetes/analytics/forecast/routes.py')

    assert 'Review utilization, capacity, workloads, consumers, and alerts.' in overview
    assert 'Review capacity and headroom while KAORI prepares analysis.' in capacity
    assert 'Review storage snapshots while KAORI prepares analytics evidence.' in storage
    assert 'Review workloads while workers prepare quota and runtime evidence.' in workload
    assert 'Review committed history while workers prepare forecast analysis.' in forecast
    assert 'Keep only provider-query dimensions in the forecast snapshot identity.' in forecast


def test_object_storage_inventory_blocker_copy_stays_compact() -> None:
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_hero.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_hero.html')

    assert 'Register a Storage integration to collect system inventory.' in systems
    assert 'Register a Storage integration to collect bucket and container inventory.' in buckets
    assert 'Review object-storage namespaces, links, and inventory snapshots.' in buckets


def test_kubernetes_analytics_routes_remain_materialized_readers() -> None:
    route_files = tuple(sorted((ROOT / 'app/kubernetes/analytics').glob('*/routes.py'))) + (
        ROOT / 'app/analytics/routes.py',
    )
    combined = '\n'.join(path.read_text(encoding='utf-8') for path in route_files)

    assert combined.count("@permission_required('analytics.view')") >= 19
    for forbidden in ('MetricsConsumer(', 'MetricsService(', '.query_range(', '.custom_query('):
        assert forbidden not in combined


def test_kubernetes_analytics_operator_copy_density_keeps_evidence_semantics() -> None:
    capacity = read('app/templates/kubernetes/analytics/capacity/partials/_overview.html')
    utilization = read('app/templates/kubernetes/analytics/utilization/partials/_overview.html')
    workload = read('app/templates/kubernetes/analytics/workload/partials/_overview.html')
    overview = read('app/templates/kubernetes/analytics/overview/partials/_capacity_snapshot.html')
    trend = read('app/templates/kubernetes/analytics/utilization/partials/_trend.html')
    forecast = read('app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html')
    ownership = read('app/templates/kubernetes/analytics/alerts/partials/_ownership_summary.html')
    links = read('app/templates/kubernetes/analytics/alerts/partials/_operational_resources.html')
    forecast_projection = read('app/kubernetes/analytics/forecast/presentation.py')
    overview_projection = read('app/kubernetes/analytics/overview/service.py')

    assert 'No immediate capacity recommendation. Recheck when demand' in overview
    assert 'Unknown capacity stays Unknown—not zero utilization or Healthy.' in utilization
    assert 'canonical node identity and validated /var or / mounts' in utilization
    assert 'ResourceQuota coverage, configured requests, memory-limit policy, QoS class' in workload
    assert 'runtime evidence, and selected-window pressure' in workload
    assert 'Critical/High-risk records before changing requests, limits, quota, or replicas' in workload
    assert 'Filesystem GiB is operational only.' in capacity
    assert 'Lowest Ready-worker scheduling margin:' in capacity
    assert 'Filesystem does not determine scheduling posture.' in capacity
    assert '{{ lowest_headroom_metric_display }}' in capacity
    assert 'destination systems control authentication, authorization, and lifecycle' in links
    assert 'Use Node Detail to locate concentrated pressure' in trend
    assert 'Signal Quality reflects historical sample completeness and variability' in forecast
    assert 'does not measure forecast accuracy' in forecast
    assert 'Missing ownership or guidance can delay assignment' in ownership

    # Keep singular/plural warning copy aligned between Forecast and Overview projections.
    expected_risk = 'may breach forecast warning thresholds.'
    for projection in (forecast_projection, overview_projection):
        assert expected_risk in projection
        assert 'risk_count != 1' in projection
        assert 'metric(s)' not in projection
