from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_side_drawer_supports_wider_widths() -> None:
    component = read('app/templates/components/side_drawer.html')
    assert "width == '2xl'" in component
    assert "width == '3xl'" in component
    assert 'max-w-4xl' in component
    assert 'max-w-5xl' in component


def test_overview_system_details_use_shared_wide_inventory_modal() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    content = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    modal = read('app/templates/components/resource_detail_modal.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert 'resource_detail_modal.detail_button(' in content
    assert "'max-w-[92rem]'" in modal
    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert (
        "detail.inventory_technical_row('Endpoint', system.endpoint, nowrap=true, class_name='lg:col-span-2')"
        in detail
    )


def test_bucket_details_use_canonical_inventory_modal_not_local_modal() -> None:
    index = read('app/templates/storage/object_storage/inventory/buckets/index.html')
    table = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    modal = read('app/templates/components/resource_detail_modal.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert 'resource_detail_modal.detail_button(' in table
    assert "'max-w-[92rem]'" in modal
    assert 'x-teleport="body"' not in table
    assert 'openDetail' not in table


def test_bucket_snapshot_source_is_compact() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    assert "'source_label': 'Committed Snapshot'" in presentation
