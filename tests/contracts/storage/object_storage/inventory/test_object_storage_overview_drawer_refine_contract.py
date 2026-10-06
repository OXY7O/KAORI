from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_object_storage_overview_is_summary_only_and_systems_owns_detail_modal() -> None:
    overview = read('app/templates/storage/object_storage/inventory/overview/index.html')
    systems_index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    systems_table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')

    assert 'resource_detail_modal.inventory_host(' not in overview
    assert '_systems_snapshot.html' not in overview
    assert 'resource_detail_modal.inventory_host(' in systems_index
    assert "url_for('object_storage_inventory.system_details', system_id=0)" in systems_index
    assert 'resource_detail_modal.detail_button(' in systems_table
    assert "url_for('object_storage_inventory.system_details', system_id=system.id)" in systems_table
    assert 'side_drawer' not in systems_table
    assert 'openDrawer' not in systems_table


def test_provider_context_keeps_endpoint_full_width_in_unified_resource_sheet() -> None:
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert (
        "detail.inventory_technical_row('Endpoint', system.endpoint, nowrap=true, class_name='lg:col-span-2')" in detail
    )
    assert "detail.inventory_row('Region', system.region)" in detail
    assert "detail.inventory_row('Addressing Style', system.addressing_style)" in detail
    assert "detail.inventory_row('Compatibility Profile', system.compatibility_profile_label, nowrap=true)" in detail
