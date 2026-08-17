from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_bucket_table_prefers_quota_over_usage_metrics() -> None:
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    table_head = template.split('<thead', 1)[1].split('</thead>', 1)[0]

    assert '>Quota<' in table_head
    assert '>Size<' not in table_head
    assert '>Objects<' not in table_head
    assert 'asset.quota.label' in template


def test_bucket_detail_modal_uses_dense_operational_information_architecture() -> None:
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')

    assert 'max-w-[88rem]' in template
    assert 'Inventory Snapshot' in template
    assert 'Asset Context' in template
    assert 'Provider Context' in template
    assert 'Protection & Access' in template
    assert 'Lifecycle & Replication' in template
    assert 'Used Size' in template
    assert 'Current Objects' in template
    assert 'Enrichment Profile' in template
    assert 'Usage Stats Mode' in template
    assert 'Quota Source' in template
    assert "detail_row('API Endpoint', asset.endpoint, break_all=true)" in template


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
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')

    assert 'collect_quota: bool = True' in client
    assert 'collect_usage_stats: bool = False' in client
    assert "get_paginator('list_objects_v2')" in client
    assert 'Quota collection is independent.' in template
    assert 'provider_metrics' in template
