from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select

from app.extensions.db import db
from app.integrations.minio.client import (
    MinioBucketSummary,
    collect_instance_bucket_inventory,
)
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem

logger = logging.getLogger(__name__)


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
        bucket.provider_created_at = summary.creation_date
        bucket.observed_at = observed_at

    for stale in existing.values():
        db.session.delete(stale)
        deleted += 1

    system.inventory_observed_at = observed_at
    db.session.flush()
    return {'created': created, 'updated': updated, 'deleted': deleted, 'total': len(observed)}


def sync_object_storage_inventory(instance: MinioInstance) -> dict[str, object]:
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
        collected = collect_instance_bucket_inventory(instance)
        current_stage = 'snapshot persistence'
        summary = commit_bucket_inventory(
            system,
            collected.buckets,
            observed_at=observed_at,
        )
        current_stage = 'commit'
        db.session.commit()
        return {
            **summary,
            'system_id': system.id,
            'system_name': system.name,
            'observed_at': observed_at.isoformat(),
            'latency_ms': collected.latency_ms,
        }
    except Exception:
        logger.exception(
            'Object-storage inventory synchronization failed for system %s during %s.',
            system.id,
            current_stage,
        )
        db.session.rollback()
        raise
