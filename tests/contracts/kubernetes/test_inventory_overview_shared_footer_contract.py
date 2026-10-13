from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_overview_cluster_footer_reuses_inventory_pagination_geometry() -> None:
    template = (
        ROOT / 'app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html'
    ).read_text()
    assert 'pagination_ui.footer_classes()' in template
    assert 'pagination_ui.summary_group_classes()' in template
    assert 'pagination_ui.navigation_group_classes()' in template
    assert 'pagination_ui.numeric_pages(' in template
    assert 'name="cluster_per_page"' in template
    assert 'resources-by-cluster-content' in template
    assert 'resources-by-cluster-loading' in template
    assert 'cluster_per_page=overview.resources_pagination.per_page' in template
