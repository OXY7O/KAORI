from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from app.extensions.db import db
from app.integrations.minio.client import MinioBucketSummary
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem


def commit_bucket_inventory(
    system: ObjectStorageSystem,
    buckets: Iterable[MinioBucketSummary],
    *,
    observed_at: datetime,
) -> dict[str, int]:
    """Replace one system's committed bucket snapshot without issuing live reads.

    Full Validation owns S3 discovery. This function only persists the already
    observed ListBuckets result so Storage Inventory remains database-backed.
    """
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
