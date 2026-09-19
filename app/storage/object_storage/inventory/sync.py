from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import TypedDict

from flask import current_app
from sqlalchemy import select

from app.extensions.db import db
from app.integrations.storage.object_storage.providers.minio.client import (
    MinioBucketSummary,
    collect_instance_bucket_inventory,
)
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem

logger = logging.getLogger(__name__)

InventoryProgressCallback = Callable[[int, int, str], None]


class ObjectStorageInventorySyncResult(TypedDict):
    created: int
    updated: int
    deleted: int
    total: int
    system_id: str
    system_name: str
    observed_at: str
    latency_ms: int
    warning_count: int
    usage_stats_mode: str


def _lock_system_inventory_sync(system_id: str) -> None:
    """Serialize one object-storage snapshot replacement inside its transaction."""
    db.session.execute(
        select(ObjectStorageSystem.id).where(ObjectStorageSystem.id == system_id).with_for_update()
    ).scalar_one()


def commit_bucket_inventory(
    system: ObjectStorageSystem,
    buckets: Iterable[MinioBucketSummary],
    *,
    observed_at: datetime,
) -> dict[str, int]:
    """Replace one system's committed bucket snapshot from already collected evidence."""
    observed = {bucket.name: bucket for bucket in buckets if bucket.name}
    existing = {bucket.name: bucket for bucket in system.buckets}

    if existing and not observed:
        raise RuntimeError(
            f'Provider bucket discovery returned zero assets while the last committed snapshot contains '
            f'{len(existing)} bucket/container asset(s). KAORI preserved the previous committed snapshot. '
            'Verify the S3 endpoint, credentials, and ListBuckets scope before retrying Object Storage Inventory Sync.'
        )

    created = 0
    updated = 0
    deleted = 0

    for name, summary in observed.items():
        bucket = existing.pop(name, None)
        if bucket is None:
            bucket = ObjectStorageBucket()
            bucket.object_storage_system_id = system.id
            bucket.name = name
            db.session.add(bucket)
            created += 1
        else:
            updated += 1
        bucket.native_type = summary.native_type or 'bucket'
        bucket.location = summary.location
        bucket.versioning_state = summary.versioning_state or 'not_collected'
        bucket.immutability_state = summary.immutability_state or 'not_collected'
        bucket.encryption_state = summary.encryption_state or 'not_collected'
        bucket.lifecycle_state = summary.lifecycle_state or 'not_collected'
        bucket.replication_state = summary.replication_state or 'not_collected'
        bucket.access_policy_state = summary.access_policy_state or 'not_collected'
        bucket.exposure_state = summary.exposure_state or 'not_collected'
        bucket.provider_metadata = dict(summary.provider_metadata or {})
        bucket.quota_bytes = summary.quota_bytes
        bucket.quota_state = summary.quota_state or 'not_collected'
        bucket.quota_source = summary.quota_source
        bucket.quota_evidence_code = summary.quota_evidence_code or 'not_collected'
        bucket.quota_checked_at = summary.quota_checked_at
        bucket.quota_observed_at = summary.quota_observed_at
        bucket.size_bytes = summary.size_bytes
        bucket.object_count = summary.object_count
        bucket.usage_stats_state = summary.usage_state or 'not_collected'
        bucket.usage_observed_at = summary.usage_observed_at
        bucket.provider_created_at = summary.creation_date
        bucket.observed_at = observed_at

    for stale in existing.values():
        db.session.delete(stale)
        deleted += 1

    system.inventory_observed_at = observed_at
    db.session.flush()
    return {'created': created, 'updated': updated, 'deleted': deleted, 'total': len(observed)}


def sync_object_storage_inventory(
    instance: MinioInstance,
    *,
    progress_callback: InventoryProgressCallback | None = None,
) -> ObjectStorageInventorySyncResult:
    """Collect and atomically commit one managed object-storage inventory snapshot.

    Job Execution owns this operation. Full Validation proves provider capability and
    Runtime Refresh observes lightweight health; neither operation commits inventory.
    """
    canonical = instance.integration_instance
    if not canonical.enabled or canonical.lifecycle_status != 'active':
        raise RuntimeError('The MinIO integration is not active for inventory synchronization.')
    if instance.readiness_status != 'ready':
        raise RuntimeError('Run Full Validation successfully before object-storage inventory synchronization.')

    system = instance.object_storage_system
    observed_at = datetime.now(UTC)
    current_stage = 'system lock'
    try:
        _lock_system_inventory_sync(system.id)
        current_stage = 'bucket discovery'
        usage_stats_mode = (
            str(current_app.config.get('OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE', 'disabled')).strip().lower()
        )
        collected = collect_instance_bucket_inventory(
            instance,
            usage_stats_mode=usage_stats_mode,
            progress_callback=progress_callback,
        )
        current_stage = 'snapshot persistence'
        summary = commit_bucket_inventory(
            system,
            collected.buckets,
            observed_at=observed_at,
        )
        current_stage = 'commit'
        db.session.commit()
        return {
            'created': summary['created'],
            'updated': summary['updated'],
            'deleted': summary['deleted'],
            'total': summary['total'],
            'system_id': system.id,
            'system_name': system.name,
            'observed_at': observed_at.isoformat(),
            'latency_ms': collected.latency_ms,
            'warning_count': collected.warning_count,
            'usage_stats_mode': collected.usage_stats_mode,
        }
    except Exception:
        logger.exception(
            'Object-storage inventory synchronization failed for system %s during %s.',
            system.id,
            current_stage,
        )
        db.session.rollback()
        raise
