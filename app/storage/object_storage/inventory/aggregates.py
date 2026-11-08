"""Committed Object Storage fleet aggregates without loading bucket ORM collections.

These read models never contact storage providers. Normalization mirrors the
Inventory presentation keys and the assessed/unknown semantics of #1263.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, case, func, or_

from app.extensions.db import db
from app.models.object_storage import ObjectStorageBucket


def _key(column: Any) -> Any:
    """Apply the same string normalization as Inventory _state_view."""
    return func.replace(func.lower(func.trim(func.coalesce(column, 'not_collected'))), '-', '_')


def bucket_fleet_posture() -> dict[str, int]:
    bucket = ObjectStorageBucket
    quota = _key(bucket.quota_state)
    versioning = _key(bucket.versioning_state)
    immutability = _key(bucket.immutability_state)
    encryption = _key(bucket.encryption_state)
    exposure = _key(bucket.exposure_state)
    positive_or_negative = ('enabled', 'configured', 'enforced', 'disabled', 'suspended', 'not_configured')
    negative = ('disabled', 'suspended', 'not_configured')
    protection_assessed = and_(
        versioning.in_(positive_or_negative),
        immutability.in_(positive_or_negative),
        encryption.in_(positive_or_negative),
    )
    attention = or_(
        exposure == 'public',
        versioning.in_(negative),
        immutability.in_(negative),
        encryption.in_(negative),
    )
    (
        total,
        assessed_quota,
        configured_quota,
        attention_count,
        assessed_protection,
        public,
        assessed_exposure,
        usage,
    ) = db.session.query(
        func.count(bucket.id),
        func.sum(case((quota.in_(('configured', 'not_configured')), 1), else_=0)),
        func.sum(case((quota == 'configured', 1), else_=0)),
        func.sum(case((attention, 1), else_=0)),
        func.sum(case((protection_assessed, 1), else_=0)),
        func.sum(case((exposure == 'public', 1), else_=0)),
        func.sum(case((exposure.in_(('public', 'private', 'restricted')), 1), else_=0)),
        func.sum(case((func.lower(func.trim(func.coalesce(bucket.usage_stats_state, ''))) == 'collected', 1), else_=0)),
    ).one()
    n, quota_count = int(total or 0), int(assessed_quota or 0)
    return {
        'total_assets': n,
        'quota_assessed': quota_count,
        'quota_configured': int(configured_quota or 0),
        'quota_gaps': max(n - quota_count, 0),
        'protection_attention': int(attention_count or 0),
        'protection_assessed': int(assessed_protection or 0),
        'public_exposure': int(public or 0),
        'exposure_assessed': int(assessed_exposure or 0),
        'usage_collected': int(usage or 0),
    }


def bucket_usage_summary(*, system_id: str | None = None) -> dict[str, int]:
    """One aggregate query for dashboard counts, usage and coverage."""
    bucket = ObjectStorageBucket
    query = db.session.query(
        func.count(bucket.id),
        func.sum(bucket.size_bytes),
        func.count(bucket.size_bytes),
        func.sum(bucket.object_count),
        func.count(bucket.object_count),
        func.sum(case((and_(bucket.quota_state == 'configured', bucket.quota_bytes.is_not(None)), 1), else_=0)),
        func.sum(case((and_(bucket.size_bytes.is_not(None), bucket.object_count.is_not(None)), 1), else_=0)),
    )
    if system_id is not None:
        query = query.filter(bucket.object_storage_system_id == system_id)
    total, size, size_count, objects, object_count, quota, usage = query.one()
    return {
        'buckets': int(total or 0),
        'stored_bytes': int(size or 0),
        'stored_samples': int(size_count or 0),
        'objects': int(objects or 0),
        'object_samples': int(object_count or 0),
        'quota_configured': int(quota or 0),
        'usage_collected': int(usage or 0),
    }


def bucket_usage_by_system(system_ids: Sequence[str]) -> dict[str, dict[str, int]]:
    """Fetch health-table bucket counts/usage for only the paginated visible systems."""
    if not system_ids:
        return {}
    bucket = ObjectStorageBucket
    rows = (
        db.session.query(
            bucket.object_storage_system_id,
            func.count(bucket.id),
            func.sum(bucket.size_bytes),
            func.count(bucket.size_bytes),
        )
        .filter(bucket.object_storage_system_id.in_(system_ids))
        .group_by(bucket.object_storage_system_id)
        .all()
    )
    return {
        system_id: {
            'buckets': int(count or 0),
            'stored_bytes': int(stored_bytes or 0),
            'stored_samples': int(samples or 0),
        }
        for system_id, count, stored_bytes, samples in rows
    }
