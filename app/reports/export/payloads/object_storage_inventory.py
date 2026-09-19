from __future__ import annotations

from typing import Any

from sqlalchemy.orm import selectinload

from app.models.object_storage import ObjectStorageSystem
from app.models.report import Report
from app.reports.catalog import require_object_storage_system, validate_report_instance


def _quota_utilization(size_bytes: int | None, quota_bytes: int | None) -> float | None:
    if size_bytes is None or quota_bytes is None or quota_bytes <= 0:
        return None
    return round((float(size_bytes) / float(quota_bytes)) * 100.0, 2)


def get_report_object_storage_inventory_payload(report: Report) -> dict[str, Any]:
    """Return committed provider-neutral Object Storage inventory only.

    Workbook/CSV rendering must never issue provider API calls. The committed
    ObjectStorageSystem/ObjectStorageBucket snapshot is the authoritative source.
    """

    validate_report_instance(report)
    system_id = require_object_storage_system(report)
    system = (
        ObjectStorageSystem.query.options(selectinload(ObjectStorageSystem.buckets))
        .filter(ObjectStorageSystem.id == system_id)
        .one_or_none()
    )
    if system is None:
        return {'_error': 'The selected Object Storage system no longer exists.'}

    rows: list[dict[str, Any]] = []
    for bucket in system.buckets or ():
        rows.append(
            {
                'system': system.name,
                'environment': system.environment,
                'asset_type': bucket.native_type or 'bucket',
                'name': bucket.name,
                'location': bucket.location,
                'size_bytes': bucket.size_bytes,
                'object_count': bucket.object_count,
                'quota_bytes': bucket.quota_bytes,
                'quota_utilization_percent': _quota_utilization(bucket.size_bytes, bucket.quota_bytes),
                'quota_state': bucket.quota_state,
                'quota_source': bucket.quota_source,
                'quota_evidence_code': bucket.quota_evidence_code,
                'versioning_state': bucket.versioning_state,
                'immutability_state': bucket.immutability_state,
                'encryption_state': bucket.encryption_state,
                'lifecycle_state': bucket.lifecycle_state,
                'replication_state': bucket.replication_state,
                'access_policy_state': bucket.access_policy_state,
                'exposure_state': bucket.exposure_state,
                'usage_stats_state': bucket.usage_stats_state,
                'provider_created_at': bucket.provider_created_at,
                'usage_observed_at': bucket.usage_observed_at,
                'quota_observed_at': bucket.quota_observed_at,
                'observed_at': bucket.observed_at,
            }
        )

    return {
        'system': {
            'id': system.id,
            'name': system.name,
            'environment': system.environment,
            'status': system.status,
        },
        'inventory_assets': rows,
        'data_cutoff': system.inventory_observed_at,
        'collected_at': system.inventory_observed_at,
        'source_label': 'Object Storage Committed Inventory',
    }
