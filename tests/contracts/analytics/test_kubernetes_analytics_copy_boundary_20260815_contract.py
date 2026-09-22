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
