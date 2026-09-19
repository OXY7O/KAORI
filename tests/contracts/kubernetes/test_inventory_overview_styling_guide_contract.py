from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_overview_uses_canonical_hero_snapshot_catalog_and_table_components() -> None:
    hero = read('app/templates/kubernetes/inventory/overview/partials/_hero.html')
    freshness = read('app/templates/kubernetes/inventory/components/_data_freshness.html')
    catalog = read('app/templates/kubernetes/inventory/overview/partials/_kpi_cards.html')
    table_shell = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster.html')

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


def test_compact_cluster_table_uses_shared_inventory_detail_modal() -> None:
    index = read('app/templates/kubernetes/inventory/overview/index.html')
    content = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html')
    detail = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    modal = read('app/templates/components/resource_detail_modal.html')

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

    assert 'resource_detail_modal.inventory_host(' in index
    assert "url_for('inventory.overview_cluster_details', cluster_id=0)" in index
    assert 'resource_detail_modal.detail_button(' in content
    assert "url_for('inventory.overview_cluster_details', cluster_id=cluster.id)" in content
    assert 'side_drawer' not in content
    assert 'openDrawer' not in content
    assert "'max-w-[92rem]'" in modal
    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert 'data-kaori-inventory-detail="v10"' in detail
    assert 'detail.inspector_summary_strip(' in detail
    assert 'detail.resource_sheet()' in detail
    assert 'Cluster Identity' in detail
    assert 'Snapshot Context' in detail
    assert 'Inventory Breakdown' in detail
    assert 'Inventory Signals' in detail
    assert 'Data Boundary' in detail
    assert 'cluster.guidance.title' in detail


def test_cluster_table_pagination_uses_resource_case_and_visible_rows_label() -> None:
    content = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html')

    assert "{{ 'Cluster' if overview.resources_pagination.total_items == 1 else 'Clusters' }}" in content
    assert '>Rows</label>' in content
    assert 'components/pagination.html' in content
    assert 'hx-indicator="#resources-by-cluster-loading"' in content


def test_inventory_overview_uses_grouped_counts_and_fresh_health_semantics() -> None:
    backend = read('app/kubernetes/inventory/overview.py')

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
    assert 'def get_inventory_overview_cluster_detail(' in backend


def test_snapshot_source_uses_unified_resource_sheet_value() -> None:
    detail = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    backend = read('app/kubernetes/inventory/overview.py')
    details_macro = read('app/templates/components/details/_detail_content.html')

    assert "'snapshot_source': 'Committed Snapshot'" in backend
    assert "detail.inventory_row('Snapshot Source', cluster.snapshot_source)" in detail
    assert "{% macro inventory_row(label, value='-', break_all=False, nowrap=False, class_name='') -%}" in details_macro
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in details_macro
    assert 'components/side_drawer.html' not in detail


def test_inventory_signals_use_resource_sheet_rows() -> None:
    detail = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')

    signals_section = detail.split("detail.inventory_section('Inventory Signals'", 1)[1].split('{% endcall %}', 1)[0]
    assert 'detail.inventory_status_row(signal.label, signal.description, signal.tone)' in signals_section
    assert 'No active inventory signals require attention.' in signals_section
    assert 'side_drawer' not in signals_section


def test_snapshot_last_collected_uses_user_datetime_in_resource_sheet() -> None:
    detail = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    presentation = read('app/bootstrap/presentation.py')

    assert "cluster.synced_at|user_datetime if cluster.synced_at else 'Not Collected'" in detail
    assert "detail.inventory_row('Last Collected'" in detail
    assert 'date_format: str | None = None' in presentation
    assert "date_format=date_format or preferences['date_format']" in presentation
