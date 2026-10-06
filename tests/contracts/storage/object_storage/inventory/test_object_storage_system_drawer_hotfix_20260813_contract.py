from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_system_detail_button_uses_canonical_async_detail_url() -> None:
    table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')

    assert 'resource_detail_modal.detail_button(' in table
    assert "url_for('object_storage_inventory.system_details', system_id=system.id)" in table
    assert 'openDrawer' not in table
    assert '@click=' not in table


def test_system_page_uses_shared_inventory_modal_host() -> None:
    index = read('app/templates/storage/object_storage/inventory/systems/index.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert "url_for('object_storage_inventory.system_details', system_id=0)" in index
    assert 'Committed Object Storage Inventory snapshot · No live provider API query.' in index


def test_legacy_system_inline_drawer_is_retired() -> None:
    table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')

    assert 'side_drawer.render(' not in table
    assert 'x_show=' not in table
    assert 'close_expression=' not in table
