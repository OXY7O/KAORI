from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_quota_diagnostics_are_persisted_as_canonical_evidence() -> None:
    model = read('app/models/object_storage.py')
    sync = read('app/storage/object_storage/inventory/sync.py')
    migration = read('migrations/versions/20260813_object_storage_quota_diagnostics.py')

    for field in ('quota_source', 'quota_evidence_code', 'quota_checked_at'):
        assert field in model
        assert field in sync
        assert field in migration
    assert "down_revision = '20260813_obj_bucket_quota'" in migration


def test_minio_quota_collector_distinguishes_operational_failure_modes() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')

    assert "api_versions = ('v3', 'v4')" in client
    assert "for field_name in ('size', 'quota')" in client
    assert "field_name == 'size' and value > 0" in client
    assert "field_name == 'quota' and value > 0" in client
    for code in (
        'access_denied',
        'signature_mismatch',
        'invalid_credentials',
        'admin_api_unreachable',
        'admin_api_timeout',
        'tls_validation_failed',
        'rate_limited',
        'invalid_response',
        'provider_error',
        'not_supported',
    ):
        assert code in client


def test_bucket_modal_surfaces_quota_source_result_and_operator_guidance() -> None:
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert "status_row('Quota Evidence', asset.quota_evidence.label, asset.quota_evidence.tone)" in template
    assert "detail_row('Quota Checked'" in template
    assert 'Quota Collection Diagnostic' in template
    assert 'asset.quota_evidence.guidance' in template
    assert 'admin:GetBucketQuota' in presentation
    assert 'Admin API Unreachable' in presentation
    assert 'Signature Mismatch' in presentation


def test_quota_source_remains_distinct_from_quota_result() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert 'MinIO Admin API v3' in presentation
    assert 'MinIO Admin API v4' in presentation
    assert "'quota_source': bucket.quota_source" in presentation
    assert "'quota_checked_at': bucket.quota_checked_at" in presentation
