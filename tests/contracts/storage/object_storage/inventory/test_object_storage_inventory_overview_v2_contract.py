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
    assert (
        'Review committed inventory coverage, readiness, and system scope across registered Object Storage environments.'
        in hero
    )
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
