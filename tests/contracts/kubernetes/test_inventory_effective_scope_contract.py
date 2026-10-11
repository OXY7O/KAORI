"""Effective cluster scope must be consistent across HTMX and full render."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_freshness_consumes_normalized_route_scope() -> None:
    routes = source('app/kubernetes/inventory/routes.py')
    assert "g.inventory_effective_cluster_id = effective_cluster_id" in routes
    assert "get_inventory_freshness_context(cluster_id=effective_cluster_id)" in routes
    assert "_inventory_cluster_scope(raw_cluster_id)" in routes
    assert "g.inventory_effective_cluster_id = context['filters']['cluster_id']" in routes
    assert "selected[0].name if cluster_id and selected_count == 1" in source(
        'app/kubernetes/inventory/overview.py'
    )


def test_unchanged_protected_htmx_route_order() -> None:
    routes = source('app/kubernetes/inventory/routes.py')
    assert "@permission_required('inventory.view')\n@_clusterless_inventory_htmx_guard" in routes
    assert "_inventory_cluster_scope(request.args.get('cluster_id', '', type=str))" in routes
