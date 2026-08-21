from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_overview_matches_final_inventory_composition() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    hero = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')
    snapshot = read('app/templates/storage/object_storage/inventory/overview/partials/_snapshot_boundary.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')
    catalog = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')
    summary = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert "url_for('object_storage_inventory.system_details', system_id=0)" in index
    assert '_fleet_posture.html' in index
    assert 'Object Storage Overview' in hero
    assert 'Systems Registered' in hero
    assert 'Inventory Assets' in hero
    assert 'Inventory Records' in hero
    assert 'Quota Evidence' in hero
    assert 'Manage Storage' in hero
    assert "url_for('integrations.storage')" in hero
    assert 'object_storage_snapshot.render(overview.snapshot)' in snapshot
    assert 'Fleet Inventory Posture' in fleet
    assert 'operational_callout.render' in fleet
    assert 'Inventory Asset Catalog' in catalog
    assert 'inventory_asset_card.render' in catalog
    assert 'Managed Systems Snapshot' in summary


def test_overview_summary_uses_canonical_table_and_shared_resource_detail() -> None:
    content = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    for heading in (
        'System',
        'Provider',
        'Inventory Assets',
        'Snapshot',
        'Status',
        'Inventory Signals',
        'Details',
    ):
        assert heading in content
    assert 'resource_detail_modal.detail_button(' in content
    assert "url_for('object_storage_inventory.system_details', system_id=system.id)" in content
    assert 'side_drawer.render(' not in content
    assert 'openDrawer' not in content
    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert 'System Identity' in detail
    assert 'Provider Connection' in detail
    assert 'Inventory Snapshot' in detail
    assert 'Authority Boundary' in detail
    assert 'system.guidance.title' in detail


def test_overview_summary_uses_kaori_pagination_and_section_loader() -> None:
    shell = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot.html')
    content = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')
    routes = read('app/storage/object_storage/inventory/routes.py')

    assert "loading_bar_id='object-storage-inventory-summary-loading'" in shell
    assert 'object-storage-inventory-summary-content' in shell
    assert 'system_per_page' in content
    assert 'Rows Per Page' in content
    assert 'pagination_ui.footer_classes()' in content
    assert 'pagination_ui.numeric_pages(' in content
    assert 'object-storage-inventory-summary-loading' in content
    assert "request.args.get('system_per_page', 5" in routes
    assert "request.headers.get('HX-Target') == 'object-storage-inventory-summary-content'" in routes


def test_overview_snapshot_and_signals_are_committed_inventory_only() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS = 24' in presentation
    assert "'source_label': 'Committed Snapshot'" in presentation
    assert "'snapshot_source': 'Committed Snapshot'" in presentation
    assert 'Inventory Not Collected' in presentation
    assert 'Stale Snapshot' in presentation
    assert 'Provider Attention' in presentation
    assert 'This detail reads committed Object Storage Inventory data.' in detail
    assert 'client.list_buckets' not in presentation


def test_overview_asset_catalog_stays_vendor_neutral() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    catalog = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')

    assert "'title': 'Systems'" in presentation
    assert "'title': 'Buckets & Containers'" in presentation
    assert 'MinIO' not in catalog
    assert 'AStor' not in catalog
    assert 'MinIO' not in fleet
    assert 'AStor' not in fleet


def test_object_storage_system_detail_uses_compact_release_and_profile_labels() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert '_release_display' in presentation
    assert '_compatibility_profile_display' in presentation
    assert "'release_label': _release_display" in presentation
    assert "'compatibility_profile_label': _compatibility_profile_display" in presentation
    assert "detail.inventory_row('Release', system.release_label, nowrap=true)" in detail
    assert "detail.inventory_row('Compatibility Profile', system.compatibility_profile_label, nowrap=true)" in detail
