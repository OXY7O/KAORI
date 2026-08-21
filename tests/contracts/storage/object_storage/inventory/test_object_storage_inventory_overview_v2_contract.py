from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_overview_is_high_level_fleet_composition() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    hero = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')
    snapshot = read('app/templates/storage/object_storage/inventory/overview/partials/_snapshot_boundary.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')
    navigation = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')

    assert '_fleet_posture.html' in index
    assert '_summary_cards.html' in index
    assert '_systems_snapshot.html' not in index
    assert 'resource_detail_modal.inventory_host(' not in index
    assert 'Object Storage Overview' in hero
    assert 'high-level committed fleet summary' in hero
    assert 'Systems Registered' in hero
    assert 'Inventory Assets' in hero
    assert 'Inventory Coverage' in hero
    assert 'Manage Storage' in hero
    assert "url_for('integrations.storage')" in hero
    assert 'object_storage_snapshot.render(overview.snapshot)' in snapshot
    assert 'Fleet Inventory Posture' in fleet
    assert 'operational_callout.render' in fleet
    assert 'Explore Object Storage Inventory' in navigation
    assert 'Overview stops at fleet posture.' in navigation
    assert 'inventory_asset_card.render' in navigation


def test_resource_level_system_detail_is_owned_by_systems_workspace() -> None:
    overview = read('app/templates/storage/object_storage/inventory/overview/index.html')
    systems_index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    systems_table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'resource_detail_modal.inventory_host(' not in overview
    assert 'resource_detail_modal.inventory_host(' in systems_index
    assert 'resource_detail_modal.detail_button(' in systems_table
    assert "url_for('object_storage_inventory.system_details', system_id=system.id)" in systems_table
    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert 'System Identity' in detail
    assert 'Provider Connection' in detail
    assert 'Inventory Snapshot' in detail
    assert 'Authority Boundary' in detail
    assert 'system.guidance.title' in detail


def test_overview_does_not_duplicate_system_pagination_or_detail_loading() -> None:
    routes = read('app/storage/object_storage/inventory/routes.py')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert 'build_overview()' in routes
    assert "request.args.get('system_page'" not in routes
    assert 'object-storage-inventory-summary-content' not in routes
    assert 'def build_overview() -> dict[str, Any]:' in presentation
    assert "'systems_pagination': pagination" not in presentation
    assert "'systems': paged_rows" not in presentation


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


def test_overview_inventory_navigation_stays_vendor_neutral() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    navigation = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')

    assert "'title': 'Systems'" in presentation
    assert "'title': 'Buckets & Containers'" in presentation
    assert 'MinIO' not in navigation
    assert 'AStor' not in navigation
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
