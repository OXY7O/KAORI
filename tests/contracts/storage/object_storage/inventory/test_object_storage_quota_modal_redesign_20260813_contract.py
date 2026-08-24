from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_bucket_table_prefers_quota_over_usage_metrics() -> None:
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    table_head = template.split('<thead', 1)[1].split('</thead>', 1)[0]

    assert '>Quota<' in table_head
    assert '>Size<' not in table_head
    assert '>Objects<' not in table_head
    assert 'asset.quota.label' in template


def test_bucket_detail_uses_dense_unified_resource_sheet_information_architecture() -> None:
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert 'data-kaori-inventory-detail="v10"' in detail
    assert 'detail.resource_sheet()' in detail
    assert "detail.inventory_section('Snapshot Context'" in detail
    assert "detail.inventory_section('Capacity & Usage'" in detail
    assert "detail.inventory_section('Provider Context'" in detail
    assert "detail.inventory_section('Data Protection'" in detail
    assert "detail.inventory_section('Lifecycle & Access'" in detail
    assert 'Used Size' in detail
    assert 'Current Objects' in detail
    assert 'Enrichment Profile' in detail
    assert 'Usage Strategy' in detail
    assert 'Quota Source' in detail
    assert "detail.inventory_technical_row('API Endpoint', bucket.endpoint" in detail


def test_quota_collection_is_minio_specific_and_optional_to_snapshot_success() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert "f'/minio/admin/{api_version}/get-bucket-quota'" in client
    assert 'admin:GetBucketQuota' in presentation
    assert 'MinioQuotaEvidence' in client
    assert "collect_quota=provider_key == 'minio'" in client
    assert "for field_name in ('size', 'quota')" in client
    assert "field_name == 'size' and value > 0" in client
    assert "field_name == 'quota' and value > 0" in client
    assert "'No Quota'" in presentation
    assert 'MinIO Admin API v3' in presentation
    assert 'MinIO Admin API v4' in presentation


def test_usage_full_scan_remains_separate_from_quota_collection() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert 'collect_quota: bool = True' in client
    assert 'collect_usage_stats: bool = False' in client
    assert "get_paginator('list_objects_v2')" in client
    assert 'Usage is collected separately from quota.' in detail
    assert 'provider_metrics' in detail
