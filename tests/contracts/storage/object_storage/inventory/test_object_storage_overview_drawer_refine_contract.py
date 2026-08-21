from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_object_storage_overview_uses_shared_inventory_modal() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    content = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert "url_for('object_storage_inventory.system_details', system_id=0)" in index
    assert 'resource_detail_modal.detail_button(' in content
    assert "url_for('object_storage_inventory.system_details', system_id=system.id)" in content
    assert 'side_drawer' not in content
    assert 'openDrawer' not in content


def test_provider_context_keeps_endpoint_full_width_in_unified_resource_sheet() -> None:
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert (
        "detail.inventory_technical_row('Endpoint', system.endpoint, nowrap=true, class_name='lg:col-span-2')"
        in detail
    )
    assert "detail.inventory_row('Region', system.region)" in detail
    assert "detail.inventory_row('Addressing Style', system.addressing_style)" in detail
    assert "detail.inventory_row('Compatibility Profile', system.compatibility_profile_label, nowrap=true)" in detail
