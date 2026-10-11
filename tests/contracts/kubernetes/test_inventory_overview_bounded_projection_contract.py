from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_sql_page_before_cluster_detail_projection() -> None:
    overview = source('app/kubernetes/inventory/overview.py')
    routes = source('app/kubernetes/inventory/routes.py')
    assert 'from app.common.pagination import paginate_query' in overview
    assert 'page_clusters, resources_pagination = paginate_query(' in overview
    assert 'for cluster in page_clusters]' in overview
    assert "'resources_pagination': resources_pagination" in overview
    assert 'paginate_sequence(' not in routes
    assert 'get_inventory_overview(cluster_page=cluster_page, cluster_per_page=cluster_per_page)' in routes


def test_one_cluster_detail_avoids_full_fleet_overview() -> None:
    overview = source('app/kubernetes/inventory/overview.py')
    detail = overview.split('def get_inventory_overview_cluster_detail(', 1)[1].split(
        'def _count_rows(', 1
    )[0]
    assert 'get_cluster_by_id(str(cluster_id))' in detail
    assert 'get_inventory_cluster_summary([cluster])' in detail
    assert '_grouped_current_counts(NodeInventory, ids)' in detail
    assert 'return _cluster_overview_row(cluster, summary, count_maps)' in detail
    assert 'get_inventory_overview(' not in detail


def test_fleet_global_counts_reuse_the_committed_grouped_sql_aggregates() -> None:
    overview = source('app/kubernetes/inventory/overview.py')
    assert "'clusters': len(clusters)" in overview
    assert "sum(per_cluster.values()) for key, per_cluster in count_maps.items()" in overview
    projection = overview.split('def get_inventory_overview(*,', 1)[1].split(
        'def get_inventory_overview_cluster_detail(', 1
    )[0]
    assert '_count_rows(' not in projection


def test_render_only_freshness_context_for_full_workspaces() -> None:
    routes = source('app/kubernetes/inventory/routes.py')
    assert "request.endpoint == 'inventory.overview'" in routes
    assert "request.endpoint.endswith('_details')" in routes
    assert "request.args.get('partial_mode') == 'table_content'" in routes
    assert "get_inventory_freshness_context(cluster_id=effective_cluster_id)" in routes
