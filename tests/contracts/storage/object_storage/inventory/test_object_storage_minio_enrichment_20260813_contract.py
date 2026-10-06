from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minio_inventory_collects_normalized_bucket_configuration_evidence() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    sync = read('app/storage/object_storage/inventory/sync.py')
    model = read('app/models/object_storage.py')

    for method in (
        'get_bucket_versioning',
        'get_bucket_encryption',
        'get_object_lock_configuration',
        'get_bucket_lifecycle_configuration',
        'get_bucket_replication',
        'get_bucket_policy',
    ):
        assert method in client
    for field in (
        'versioning_state',
        'immutability_state',
        'encryption_state',
        'lifecycle_state',
        'replication_state',
        'access_policy_state',
        'exposure_state',
    ):
        assert field in model
        assert f'bucket.{field} = summary.{field}' in sync
    assert 'MinIO Bucket Configuration' in client
    assert 'enrichment_gaps' in client


def test_bucket_usage_stats_are_optional_and_persisted_canonically() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    config = read('app/config/default.py')
    model = read('app/models/object_storage.py')
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert 'OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE' in config
    assert "{'disabled', 'provider_metrics', 'full_scan'}" in config
    assert "get_paginator('list_objects_v2')" in client
    assert "f'/minio/admin/{api_version}/datausageinfo'" in client
    assert "payload.get('bucketsUsageInfo')" in client
    assert 'size_bytes' in model
    assert 'object_count' in model
    assert 'usage_stats_state' in model
    assert "'size_label': _format_bytes(bucket.size_bytes)" in presentation
    assert "'object_count_label': _format_count(bucket.object_count)" in presentation
    assert '>Quota<' in template
    assert '>Size<' not in template.split('<thead', 1)[1].split('</thead>', 1)[0]
    assert '>Objects<' not in template.split('<thead', 1)[1].split('</thead>', 1)[0]
    assert 'Used Size' in detail
    assert 'Current Objects' in detail


def test_bucket_and_system_detail_surfaces_share_the_inventory_modal_contract() -> None:
    bucket_index = read('app/templates/storage/object_storage/inventory/buckets/index.html')
    system_index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')

    assert 'resource_detail_modal.inventory_host(' in bucket_index
    assert 'resource_detail_modal.inventory_host(' in system_index
    assert 'resource_detail_modal.detail_button(' in buckets
    assert 'resource_detail_modal.detail_button(' in systems
    assert 'side_drawer.render(' not in buckets
    assert 'side_drawer.render(' not in systems


def test_enrichment_migration_extends_current_bucket_container_head() -> None:
    migration = read('migrations/versions/20260813_object_storage_bucket_enrichment.py')
    assert "revision = '20260813_obj_bucket_enrichment'" in migration
    assert "down_revision = '20260813_obj_asset_contract'" in migration
    assert "'size_bytes'" in migration
    assert "'object_count'" in migration
    assert "'usage_stats_state'" in migration


def test_minio_bucket_quota_is_canonical_inventory_evidence() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    model = read('app/models/object_storage.py')
    sync = read('app/storage/object_storage/inventory/sync.py')
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    migration = read('migrations/versions/20260813_object_storage_bucket_quota.py')

    assert "f'/minio/admin/{api_version}/get-bucket-quota'" in client
    assert 'admin:GetBucketQuota' in client
    for field in (
        'quota_bytes',
        'quota_state',
        'quota_source',
        'quota_evidence_code',
        'quota_checked_at',
        'quota_observed_at',
    ):
        assert field in model
        assert f'bucket.{field} = summary.{field}' in sync
    assert 'def _quota_view' in presentation
    assert "revision = '20260813_obj_bucket_quota'" in migration
    assert "down_revision = '20260813_obj_bucket_enrichment'" in migration
