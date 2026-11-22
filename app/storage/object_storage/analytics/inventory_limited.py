"""Read-only Object Storage Analytics Inventory coverage for Limited Overview (#5124).

This domain-owned query stays bounded by one selected system. It must not
reinterpret missing stored-size or object-count observations as a healthy zero.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.extensions.db import db
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
from app.storage.object_storage.analytics.presentation import format_bytes, format_number


def inventory_limited_coverage(
    *,
    bucket_count: int,
    size_observed: int,
    size_total: int | None,
    objects_observed: int,
    objects_total: int | None,
) -> dict[str, str | int]:
    """Summarize only complete committed inventory fields, never guessed missing values."""
    size_complete = size_observed == bucket_count
    objects_complete = objects_observed == bucket_count
    size_value = int(size_total or 0) if size_complete else None
    objects_value = int(objects_total or 0) if objects_complete else None
    return {
        'bucket_count': bucket_count,
        'bucket_count_display': format_number(bucket_count),
        'size_display': format_bytes(size_value) if size_value is not None else 'N/A',
        'objects_display': format_number(objects_value) if objects_value is not None else 'N/A',
        'size_coverage': f'{size_observed} / {bucket_count} buckets',
        'objects_coverage': f'{objects_observed} / {bucket_count} buckets',
        'size_status': 'Observed' if size_complete else 'Incomplete',
        'objects_status': 'Observed' if objects_complete else 'Incomplete',
    }


def build_inventory_limited_view(system: ObjectStorageSystem) -> dict[str, str | int]:
    """One system-bound SQL aggregate; no full bucket ORM load on a normal GET."""
    summary = (
        db.session.query(
            func.count(ObjectStorageBucket.id),
            func.count(ObjectStorageBucket.size_bytes),
            func.sum(ObjectStorageBucket.size_bytes),
            func.count(ObjectStorageBucket.object_count),
            func.sum(ObjectStorageBucket.object_count),
        )
        .filter(ObjectStorageBucket.object_storage_system_id == system.id)
        .one()
    )
    return inventory_limited_coverage(
        bucket_count=int(summary[0] or 0),
        size_observed=int(summary[1] or 0),
        size_total=int(summary[2]) if summary[2] is not None else None,
        objects_observed=int(summary[3] or 0),
        objects_total=int(summary[4]) if summary[4] is not None else None,
    )


def limited_inventory_analytics_context(
    context: dict[str, Any], system: ObjectStorageSystem
) -> dict[str, Any]:
    """Preserve separately committed Inventory while metric evidence is unavailable."""
    context['analytics_limited'] = True
    context['dependency_blocker'] = None
    context['inventory_limited'] = build_inventory_limited_view(system)
    context['metrics_source'] = {
        **context['metrics_source'],
        'label': 'Not Collected',
        'tone': 'unknown',
        'detail': 'No committed Metrics Source collection evidence for the selected window.',
    }
    context['metrics_readiness'] = {
        **context['metrics_readiness'],
        'label': 'Not Collected',
        'tone': 'unknown',
        'detail': 'The missing Analytics snapshot does not prove source binding is absent.',
    }
    return context
