from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_kubernetes_analytics_copy_refinement_is_concise_and_domain_specific() -> None:
    overview = read('app/templates/analytics/kubernetes/overview/partials/_hero.html')
    capacity = read('app/analytics/kubernetes/capacity/routes.py')
    storage = read('app/analytics/kubernetes/storage/routes.py')
    workload = read('app/analytics/kubernetes/workload/routes.py')
    forecast = read('app/analytics/kubernetes/forecast/routes.py')

    assert (
        'Review consolidated resource utilization, workload posture, storage, forecasts, top consumers, and alert signals.'
        in overview
    )
    assert 'shared capacity, allocation, and headroom results' in capacity
    assert 'committed operational snapshots' in storage
    assert 'committed quota, runtime, and resource snapshots' in workload
    assert 'selected cluster, namespace, and window' in forecast
    assert 'Horizon, model, and resource tabs remain presentation-only.' in forecast


def test_object_storage_inventory_blocker_copy_stays_compact() -> None:
    systems = read('app/templates/inventory/object_storage/systems/partials/_hero.html')
    buckets = read('app/templates/inventory/object_storage/buckets/partials/_hero.html')

    assert 'Register a Storage integration to collect system inventory.' in systems
    assert 'Register a Storage integration to collect bucket and container inventory.' in buckets
    assert (
        'Review provider-neutral object-storage namespaces, asset coverage, and relationships from committed inventory snapshots.'
        in buckets
    )


def test_kubernetes_analytics_routes_remain_materialized_readers() -> None:
    route_files = tuple(sorted((ROOT / 'app/analytics/kubernetes').glob('*/routes.py'))) + (
        ROOT / 'app/analytics/routes.py',
    )
    combined = '\n'.join(path.read_text(encoding='utf-8') for path in route_files)

    assert combined.count("@permission_required('analytics.view')") >= 19
    for forbidden in ('MetricsConsumer(', 'MetricsService(', '.query_range(', '.custom_query('):
        assert forbidden not in combined
