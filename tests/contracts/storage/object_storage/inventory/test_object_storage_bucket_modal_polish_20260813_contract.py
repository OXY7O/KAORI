from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_bucket_detail_uses_shared_wide_inventory_modal_and_unified_resource_sheet() -> None:
    index = read('app/templates/storage/object_storage/inventory/buckets/index.html')
    modal = read('app/templates/components/resource_detail_modal.html')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert "'max-w-[92rem]'" in modal
    assert 'data-kaori-inventory-detail="v10"' in detail
    assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
    assert 'detail.resource_sheet()' in detail
    assert 'overflow-y-auto' not in detail
    assert 'x-teleport="body"' not in index


def test_provider_configuration_uses_full_width_resource_sheet_rows() -> None:
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert "detail.inventory_section('Provider Context'" in detail
    assert 'Bucket identity, provider system, native type, location, environment, and creation context.' in detail
    assert "detail.inventory_technical_row('API Endpoint', bucket.endpoint" in detail
    assert "class_name='lg:col-span-2'" in detail
    assert 'provider_detail_sections' in detail
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated' not in detail


def test_bucket_detail_keeps_operational_guidance_without_card_gallery() -> None:
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert "detail.inventory_section('Capacity & Usage'" in detail
    assert 'bucket.quota_evidence.label' in detail
    assert 'bucket.quota_evidence.guidance' in detail
    assert 'provider_metrics' in detail
    assert 'full_scan' in detail
    assert 'Partial Provider Evidence' in detail
    assert "operational_callout.render('Inventory Boundary'" in detail
    assert "operational_callout.render('Recommended Action'" in detail
    assert 'operational_section_card.render(' not in detail
