from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_overview_matches_kubernetes_inventory_composition() -> None:
    index = read('app/templates/object_storage_inventory/overview/index.html')
    hero = read('app/templates/object_storage_inventory/overview/partials/_hero.html')
    snapshot = read('app/templates/object_storage_inventory/overview/partials/_snapshot_boundary.html')
    catalog = read('app/templates/object_storage_inventory/overview/partials/_summary_cards.html')
    summary = read('app/templates/object_storage_inventory/overview/partials/_systems_snapshot.html')

    assert 'resource_detail_modal' not in index
    assert 'Object Storage Overview' in hero
    assert 'Systems Registered' in hero
    assert 'Asset Types' in hero
    assert 'Inventory Records' in hero
    assert 'Manage Storage' in hero
    assert "url_for('integrations.storage')" in hero
    assert 'snapshot_context_bar.render' in snapshot
    assert 'Inventory Asset Catalog' in catalog
    assert 'inventory_asset_card.render' in catalog
    assert 'Object Storage Inventory Summary' in summary


def test_overview_summary_uses_kubernetes_style_table_and_side_drawer() -> None:
    content = read('app/templates/object_storage_inventory/overview/partials/_systems_snapshot_content.html')

    for heading in (
        'System',
        'Connection',
        'Product',
        'Total Buckets',
        'Last Snapshot',
        'Inventory Signals',
        'Details',
    ):
        assert heading in content
    assert 'side_drawer.render(' in content
    assert 'resource_detail_modal' not in content
    assert 'View Details' in content
    assert 'System Snapshot Summary' in content
    assert 'System Identity' in content
    assert 'Snapshot Context' in content
    assert 'Provider Context' in content
    assert 'Inventory Breakdown' in content
    assert 'Inventory Signals' in content
    assert 'Operational Context' in content
    assert 'Open Provider Integration' in content
    assert "url_for('minio.instance_detail'" in content


def test_overview_summary_uses_kaori_pagination_and_section_loader() -> None:
    shell = read('app/templates/object_storage_inventory/overview/partials/_systems_snapshot.html')
    content = read('app/templates/object_storage_inventory/overview/partials/_systems_snapshot_content.html')
    routes = read('app/storage_inventory/routes.py')

    assert "loading_bar_id='object-storage-inventory-summary-loading'" in shell
    assert 'object-storage-inventory-summary-content' in shell
    assert 'system_per_page' in content
    assert 'Rows per page' in content
    assert 'pagination_ui.numeric_pages(' in content
    assert 'object-storage-inventory-summary-loading' in content
    assert "request.args.get('system_per_page', 5" in routes
    assert "request.headers.get('HX-Target') == 'object-storage-inventory-summary-content'" in routes


def test_overview_snapshot_and_signals_are_committed_inventory_only() -> None:
    presentation = read('app/storage_inventory/presentation.py')
    content = read('app/templates/object_storage_inventory/overview/partials/_systems_snapshot_content.html')

    assert 'OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS = 24' in presentation
    assert "'source_label': 'Committed Object Storage Snapshot'" in presentation
    assert "'snapshot_source': 'Committed Snapshot'" in presentation
    assert 'Inventory Not Collected' in presentation
    assert 'Stale Snapshot' in presentation
    assert 'Provider Attention' in presentation
    assert 'does not query the object-storage provider API live' in content
    assert 'client.list_buckets' not in presentation


def test_overview_asset_catalog_stays_vendor_neutral() -> None:
    presentation = read('app/storage_inventory/presentation.py')
    catalog = read('app/templates/object_storage_inventory/overview/partials/_summary_cards.html')

    assert "'title': 'Systems'" in presentation
    assert "'title': 'Buckets'" in presentation
    assert 'MinIO' not in catalog
    assert 'AStor' not in catalog


def test_object_storage_drawer_uses_compact_release_and_profile_labels() -> None:
    presentation = read('app/storage_inventory/presentation.py')
    overview = read('app/templates/object_storage_inventory/overview/partials/_systems_snapshot_content.html')
    systems = read('app/templates/object_storage_inventory/systems/partials/_system_detail_content.html')

    assert '_release_display' in presentation
    assert '_compatibility_profile_display' in presentation
    assert "'release_label': _release_display" in presentation
    assert "'compatibility_profile_label': _compatibility_profile_display" in presentation
    assert "detail_ui.detail_row('Release', system.release_label)" in overview
    assert "detail_ui.detail_row('Profile', system.compatibility_profile_label)" in overview
    assert "detail.detail_row('Release', system.release_label)" in systems
    assert "detail.detail_row('Profile', system.compatibility_profile_label)" in systems
