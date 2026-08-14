from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_overview_matches_final_inventory_composition() -> None:
    index = read('app/templates/inventory/object_storage/overview/index.html')
    hero = read('app/templates/inventory/object_storage/overview/partials/_hero.html')
    snapshot = read('app/templates/inventory/object_storage/overview/partials/_snapshot_boundary.html')
    fleet = read('app/templates/inventory/object_storage/overview/partials/_fleet_posture.html')
    catalog = read('app/templates/inventory/object_storage/overview/partials/_summary_cards.html')
    summary = read('app/templates/inventory/object_storage/overview/partials/_systems_snapshot.html')

    assert 'resource_detail_modal' not in index
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


def test_overview_summary_uses_canonical_table_and_side_drawer() -> None:
    content = read('app/templates/inventory/object_storage/overview/partials/_systems_snapshot_content.html')

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
    assert 'side_drawer.render(' in content
    assert 'resource_detail_modal' not in content
    assert 'View Details' in content
    assert 'System Snapshot Summary' in content
    assert 'System Identity' in content
    assert 'Inventory Snapshot' in content
    assert 'Provider Context' in content
    assert 'Operational Reading' in content
    assert 'Operational Context' in content
    assert 'Authority Boundary' in content
    assert 'Related Operational Workspace' in content
    assert 'Open Provider Integration' in content
    assert "url_for('minio.instance_detail'" in content
    assert "url_for('jobs.configuration', job_key='object_storage.inventory.sync')" in content


def test_overview_summary_uses_kaori_pagination_and_section_loader() -> None:
    shell = read('app/templates/inventory/object_storage/overview/partials/_systems_snapshot.html')
    content = read('app/templates/inventory/object_storage/overview/partials/_systems_snapshot_content.html')
    routes = read('app/inventory/object_storage/routes.py')

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
    presentation = read('app/inventory/object_storage/presentation.py')
    content = read('app/templates/inventory/object_storage/overview/partials/_systems_snapshot_content.html')

    assert 'OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS = 24' in presentation
    assert "'source_label': 'Committed Snapshot'" in presentation
    assert "'snapshot_source': 'Committed Snapshot'" in presentation
    assert 'Inventory Not Collected' in presentation
    assert 'Stale Snapshot' in presentation
    assert 'Provider Attention' in presentation
    assert 'This drawer reads committed Object Storage Inventory data.' in content
    assert 'client.list_buckets' not in presentation


def test_overview_asset_catalog_stays_vendor_neutral() -> None:
    presentation = read('app/inventory/object_storage/presentation.py')
    catalog = read('app/templates/inventory/object_storage/overview/partials/_summary_cards.html')
    fleet = read('app/templates/inventory/object_storage/overview/partials/_fleet_posture.html')

    assert "'title': 'Systems'" in presentation
    assert "'title': 'Buckets & Containers'" in presentation
    assert 'MinIO' not in catalog
    assert 'AStor' not in catalog
    assert 'MinIO' not in fleet
    assert 'AStor' not in fleet


def test_object_storage_drawer_uses_compact_release_and_profile_labels() -> None:
    presentation = read('app/inventory/object_storage/presentation.py')
    overview = read('app/templates/inventory/object_storage/overview/partials/_systems_snapshot_content.html')

    assert '_release_display' in presentation
    assert '_compatibility_profile_display' in presentation
    assert "'release_label': _release_display" in presentation
    assert "'compatibility_profile_label': _compatibility_profile_display" in presentation
    assert "detail_ui.detail_row('Release', system.release_label)" in overview
    assert "detail_ui.detail_row('Profile', system.compatibility_profile_label)" in overview
