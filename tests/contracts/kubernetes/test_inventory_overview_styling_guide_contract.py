from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_overview_uses_canonical_hero_snapshot_catalog_and_table_components() -> None:
    hero = read('app/templates/inventory/overview/partials/_hero.html')
    freshness = read('app/templates/inventory/components/_data_freshness.html')
    catalog = read('app/templates/inventory/overview/partials/_kpi_cards.html')
    table_shell = read('app/templates/inventory/overview/partials/_resources_by_cluster.html')

    assert 'page_hero.context_card' in hero
    assert 'Last Sync' not in hero
    assert "'Coverage'" not in hero
    assert "'Freshness'" not in hero
    assert "'Active Signals'" in hero
    assert 'Asset Types' in hero
    assert 'components/snapshot_context_bar.html' in freshness
    assert 'components/inventory_asset_card.html' in catalog
    assert 'components/operational_section_card.html' in catalog
    assert 'components/operational_section_card.html' in table_shell
    assert "'Cluster Inventory Summary'" in table_shell


def test_compact_cluster_table_has_details_button_and_shared_right_drawer() -> None:
    content = read('app/templates/inventory/overview/partials/_resources_by_cluster_content.html')
    drawer = read('app/templates/components/side_drawer.html')

    expected_headers = (
        'Cluster',
        'Connection',
        'Total Objects',
        'Last Snapshot',
        'Inventory Signals',
        'Details',
    )
    for header in expected_headers:
        assert f'>{header}<' in content

    removed_headers = (
        '>Nodes<',
        '>Namespaces<',
        '>Workloads<',
        '>Pods<',
        '>Services<',
        '>Ingresses<',
        '>Storage<',
        '>Risk Hints<',
    )
    for removed_header in removed_headers:
        assert removed_header not in content

    assert 'View Details' in content
    assert 'components/side_drawer.html' in content
    assert 'Inventory Breakdown' in content
    assert 'Snapshot Context' in content
    assert 'Cluster Snapshot Summary' in content
    assert 'Largest Segment' in content
    assert 'Operational Context' in content
    assert 'Data Boundary' in content
    assert 'cluster.guidance.title' in content
    assert 'Open Cluster Inventory' in content
    assert 'role="dialog"' in drawer
    assert 'aria-modal="true"' in drawer
    assert '{% macro section(' in drawer
    assert '{% macro metric(' in drawer
    assert "density='default'" in drawer
    assert "variant='card'" in drawer
    assert "variant='plain'" in content
    assert "'Committed inventory overview.'" in content
    assert "'Platform and registration context for the selected inventory source.'" not in content
    assert "'Collection boundary and freshness for the committed generation.'" not in content


def test_cluster_table_pagination_uses_resource_case_and_visible_rows_label() -> None:
    content = read('app/templates/inventory/overview/partials/_resources_by_cluster_content.html')

    assert "{{ 'Cluster' if overview.resources_pagination.total_items == 1 else 'Clusters' }}" in content
    assert '>Rows</label>' in content
    assert 'components/pagination.html' in content
    assert 'hx-indicator="#resources-by-cluster-loading"' in content


def test_inventory_overview_uses_grouped_counts_and_fresh_health_semantics() -> None:
    backend = read('app/inventory/overview.py')

    assert 'def _grouped_current_counts(' in backend
    assert '.group_by(model.cluster_id)' in backend
    assert 'def _cluster_resource_counts(' not in backend
    assert 'ConfigurationInventory' in backend
    assert "'asset_catalog': asset_catalog" in backend
    assert "'configuration': _grouped_current_counts(ConfigurationInventory, cluster_ids)" in backend
    assert 'if connected:' in backend
    assert 'healthy_clusters += 1' in backend
    assert 'def _inventory_guidance(' in backend
    assert "'active_signal_count': active_signal_count" in backend
    assert "'dominant_asset': dominant_asset" in backend


def test_snapshot_source_uses_non_wrapping_detail_value() -> None:
    content = read('app/templates/inventory/overview/partials/_resources_by_cluster_content.html')
    details_macro = read('app/templates/components/details/_detail_content.html')

    assert "detail_row('Snapshot Source', cluster.snapshot_source, wrap=False)" in content
    assert "{% macro detail_row(label, value='-', break_all=False, wrap=True) -%}" in details_macro
    assert "'break-words [overflow-wrap:anywhere]' if wrap else 'whitespace-nowrap'" in details_macro
