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

def test_bucket_detail_header_and_section_labels_follow_kubernetes_inventory_standard() -> None:
    table = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_card.html')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')
    host = read('app/templates/storage/object_storage/inventory/buckets/index.html')

    assert 'Compare bucket and container records; view provider evidence in Details.' in table
    assert 'Committed Object Storage Inventory snapshot · No live provider API query.' in host
    assert "detail.workspace_header(detail_description, 'container'," in detail
    assert 'context_items=[' in detail
    assert "'label': bucket.system_name" in detail
    assert "'label': bucket.provider_label" in detail
    assert "'label': bucket.native_type_label" in detail
    assert 'compact=true) %}' in detail
    assert 'detail.inventory_title(bucket.name, compact=true)' in detail
    assert 'detail.header_identity_row()' in detail
    assert "status_indicator_label(bucket.protection.label, bucket.protection.tone, size='detail')" in detail

    # A badge must be backed by the corresponding committed field, never a synthetic Healthy state.
    badges = (
        ("'Identity & Location', 'badge-info', bucket.native_type_label", "metadata"),
        ("'Snapshot Context', 'clock-3', bucket.snapshot_status_label, 'status'", "status"),
        ("'Capacity & Usage', 'chart-no-axes-column', bucket.usage_state.label, 'status'", "status"),
        ("'Data Protection', 'shield-check', bucket.protection.label, 'status'", "status"),
        ("'Lifecycle & Access', 'git-branch', bucket.access_policy.label, 'status'", "status"),
        ("'Provider Context', 'database-zap', bucket.provider_label", "metadata"),
        ("section.title, section.icon, bucket.provider_label", "metadata"),
    )
    for rendered_section, _badge_kind in badges:
        assert rendered_section in detail
    assert detail.count("badge_size='detail', stretch=false, density='compact'") == 7
    assert "bucket.provider_detail_sections" in detail
    assert "detail.inventory_row('Quota', bucket.quota.label)" in detail
    assert 'whitespace-nowrap' not in table
