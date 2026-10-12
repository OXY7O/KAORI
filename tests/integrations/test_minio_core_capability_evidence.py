"""MinIO Core Validation must not claim optional S3 reads it did not probe."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.integrations.storage.object_storage.providers.minio.application.presentation import (
    build_minio_capability_registry,
)


def test_optional_bucket_capabilities_are_not_checked_after_core_validation() -> None:
    instance = SimpleNamespace(
        capabilities=['s3_api', 'bucket_discovery'],
        last_validated_at=datetime.now(UTC),
    )
    registry = build_minio_capability_registry(instance, per_page=50)
    rows = {row['key']: row for row in registry['rows']}

    assert rows['s3_api']['status'] == 'ready'
    assert rows['bucket_discovery']['status'] == 'ready'
    for key in (
        'bucket_versioning_read',
        'bucket_lifecycle_read',
        'bucket_policy_read',
        'bucket_encryption_read',
        'bucket_object_lock_read',
    ):
        assert rows[key]['status'] == 'not_checked'
        assert rows[key]['available'] is False
    assert registry['ready_count'] == 2
    filtered = build_minio_capability_registry(instance, status='not_checked', per_page=50)
    assert all(row['status'] == 'not_checked' for row in filtered['rows'])


def test_missing_required_capability_is_blocked_only_after_validation() -> None:
    instance = SimpleNamespace(capabilities=[], last_validated_at=None)
    pending = build_minio_capability_registry(instance, per_page=50)
    assert all(row['status'] == 'not_checked' for row in pending['rows'])
    instance.last_validated_at = datetime.now(UTC)
    failed = build_minio_capability_registry(instance, per_page=50)
    rows = {row['key']: row for row in failed['rows']}
    assert rows['s3_api']['status'] == 'blocked'
    assert rows['bucket_versioning_read']['status'] == 'not_checked'
