from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_bucket_modal_uses_shared_wide_layout_and_natural_height_detail() -> None:
    index = read('app/templates/storage/object_storage/inventory/buckets/index.html')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')
    modal = read('app/templates/components/resource_detail_modal.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert "'max-w-[92rem]'" in modal
    assert 'content_driven' in modal
    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert 'overflow-y-auto' not in detail


def test_system_details_reuse_systems_unified_resource_sheet() -> None:
    index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert 'resource_detail_modal.detail_button(' in table
    assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
    assert "detail.inventory_row('Compatibility Profile', system.compatibility_profile_label, nowrap=true)" in detail
    assert (
        "detail.inventory_technical_row('Endpoint', system.endpoint, nowrap=true, class_name='lg:col-span-2')" in detail
    )


def test_bucket_presentation_uses_short_snapshot_source_label() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    assert "'source_label': 'Committed Snapshot'" in presentation
