from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.common.pagination import paginate_sequence
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem

_PRODUCT_LABELS = {
    'minio': 'MinIO',
    'astor': 'AStor',
    's3_compatible': 'S3-Compatible',
}
_STATUS_LABELS = {
    'connected': ('Ready', 'normal'),
    'ready': ('Ready', 'normal'),
    'blocked': ('Blocked', 'critical'),
    'failed': ('Failed', 'critical'),
    'warning': ('Attention', 'warning'),
    'unknown': ('Not Observed', 'unknown'),
}


def _product_label(value: str | None) -> str:
    key = str(value or '').strip().lower()
    return _PRODUCT_LABELS.get(key, key.replace('_', ' ').title() if key else 'Not Observed')


def _status(value: str | None) -> tuple[str, str]:
    key = str(value or 'unknown').strip().lower()
    return _STATUS_LABELS.get(key, (key.replace('_', ' ').title(), 'info'))


def _system_query():
    return ObjectStorageSystem.query.options(
        joinedload(ObjectStorageSystem.minio_connection),
        selectinload(ObjectStorageSystem.buckets),
    ).order_by(ObjectStorageSystem.name.asc())


def _system_row(system: ObjectStorageSystem) -> dict[str, Any]:
    connection = system.minio_connection
    status_label, status_tone = _status(system.status)
    buckets = list(system.buckets or ())
    latest_observed_at = system.inventory_observed_at
    return {
        'id': system.id,
        'name': system.name,
        'description': system.description or '',
        'environment': system.environment,
        'status': system.status,
        'status_label': status_label,
        'status_tone': status_tone,
        'product_key': str(connection.detected_product or '') if connection is not None else '',
        'product_label': _product_label(connection.detected_product if connection is not None else None),
        'release': (
            connection.declared_release if connection is not None and connection.declared_release else 'Not Declared'
        ),
        'endpoint': connection.endpoint if connection is not None else 'Not Configured',
        'region': connection.region if connection is not None else 'Not Observed',
        'addressing_style': (
            str(connection.addressing_style or 'path').replace('_', ' ').title()
            if connection is not None
            else 'Not Observed'
        ),
        'compatibility_profile': (
            connection.compatibility_profile
            if connection is not None and connection.compatibility_profile
            else 'Not Resolved'
        ),
        'readiness_status': (
            connection.readiness_status
            if connection is not None and connection.readiness_status
            else 'validation_required'
        ),
        'bucket_count': len(buckets),
        'last_inventory_at': latest_observed_at,
        'last_validated_at': connection.last_validated_at if connection is not None else None,
        'last_checked_at': connection.last_checked_at if connection is not None else None,
        'provider_connection_id': connection.id if connection is not None else None,
    }


def _system_filter_options(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    products = sorted({row['product_key'] for row in rows if row['product_key']})
    environments = sorted({str(row['environment']) for row in rows if row['environment']})
    statuses = sorted({str(row['status']) for row in rows if row['status']})
    return {
        'products': [{'value': value, 'label': _product_label(value)} for value in products],
        'environments': [{'value': value, 'label': value.title()} for value in environments],
        'statuses': [{'value': value, 'label': _status(value)[0]} for value in statuses],
    }


def build_overview() -> dict[str, Any]:
    rows = [_system_row(system) for system in _system_query().all()]
    total_systems = len(rows)
    total_buckets = sum(int(row['bucket_count']) for row in rows)
    ready_systems = sum(1 for row in rows if row['status_tone'] == 'normal')
    blocked_systems = sum(1 for row in rows if row['status_tone'] == 'critical')
    inventoried_systems = sum(1 for row in rows if row['last_inventory_at'] is not None)
    coverage = round((inventoried_systems / total_systems) * 100) if total_systems else 0
    latest_inventory_at = max(
        (row['last_inventory_at'] for row in rows if row['last_inventory_at'] is not None),
        default=None,
    )

    if total_systems == 0:
        posture_label, posture_tone = 'No Sources', 'unknown'
    elif blocked_systems:
        posture_label, posture_tone = 'Attention Required', 'warning'
    elif inventoried_systems < total_systems:
        posture_label, posture_tone = 'Inventory Pending', 'warning'
    else:
        posture_label, posture_tone = 'Ready', 'normal'

    return {
        'total_systems': total_systems,
        'total_buckets': total_buckets,
        'ready_systems': ready_systems,
        'blocked_systems': blocked_systems,
        'inventoried_systems': inventoried_systems,
        'inventory_coverage': coverage,
        'latest_inventory_at': latest_inventory_at,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'systems': rows[:5],
    }


@dataclass(frozen=True, slots=True)
class SystemFilters:
    search: str = ''
    product: str = ''
    environment: str = ''
    status: str = ''
    page: int = 1
    per_page: int = 5


def build_systems(filters: SystemFilters) -> dict[str, Any]:
    all_rows = [_system_row(system) for system in _system_query().all()]
    options = _system_filter_options(all_rows)
    search = filters.search.strip().lower()
    rows = [
        row
        for row in all_rows
        if (not search or search in ' '.join((row['name'], row['endpoint'], row['product_label'])).lower())
        and (not filters.product or row['product_key'] == filters.product)
        and (not filters.environment or row['environment'] == filters.environment)
        and (not filters.status or row['status'] == filters.status)
    ]
    paged, pagination = paginate_sequence(rows, page=filters.page, per_page=filters.per_page)
    return {
        'systems': paged,
        'pagination': pagination,
        'total_systems': len(rows),
        'ready_systems': sum(1 for row in rows if row['status_tone'] == 'normal'),
        'blocked_systems': sum(1 for row in rows if row['status_tone'] == 'critical'),
        'inventoried_systems': sum(1 for row in rows if row['last_inventory_at'] is not None),
        **options,
    }


def build_system_detail(system_id: str) -> dict[str, Any] | None:
    system = _system_query().filter(ObjectStorageSystem.id == system_id).first()
    return _system_row(system) if system is not None else None


def _bucket_row(bucket: ObjectStorageBucket) -> dict[str, Any]:
    system = bucket.object_storage_system
    connection = system.minio_connection
    return {
        'id': bucket.id,
        'name': bucket.name,
        'system_id': system.id,
        'system_name': system.name,
        'environment': system.environment,
        'product_key': str(connection.detected_product or '') if connection is not None else '',
        'product_label': _product_label(connection.detected_product if connection is not None else None),
        'provider_created_at': bucket.provider_created_at,
        'observed_at': bucket.observed_at,
        'region': connection.region if connection is not None else 'Not Observed',
        'endpoint': connection.endpoint if connection is not None else 'Not Configured',
        'source_label': 'Full Validation Snapshot',
    }


@dataclass(frozen=True, slots=True)
class BucketFilters:
    search: str = ''
    system_id: str = ''
    product: str = ''
    environment: str = ''
    page: int = 1
    per_page: int = 5


def build_buckets(filters: BucketFilters) -> dict[str, Any]:
    systems = _system_query().all()
    system_rows = [_system_row(system) for system in systems]
    system_by_id = {system.id: system for system in systems}
    buckets = (
        ObjectStorageBucket.query.options(
            joinedload(ObjectStorageBucket.object_storage_system).joinedload(ObjectStorageSystem.minio_connection)
        )
        .order_by(ObjectStorageBucket.name.asc())
        .all()
    )
    rows = [_bucket_row(bucket) for bucket in buckets]
    search = filters.search.strip().lower()
    filtered = [
        row
        for row in rows
        if (not search or search in f'{row["name"]} {row["system_name"]} {row["product_label"]}'.lower())
        and (not filters.system_id or row['system_id'] == filters.system_id)
        and (not filters.product or row['product_key'] == filters.product)
        and (not filters.environment or row['environment'] == filters.environment)
    ]
    paged, pagination = paginate_sequence(filtered, page=filters.page, per_page=filters.per_page)
    return {
        'buckets': paged,
        'pagination': pagination,
        'total_buckets': len(filtered),
        'systems_in_scope': len({row['system_id'] for row in filtered}),
        'products_in_scope': len({row['product_key'] for row in filtered if row['product_key']}),
        'latest_observed_at': max(
            (row['observed_at'] for row in filtered if row['observed_at'] is not None),
            default=None,
        ),
        'systems': [{'id': row['id'], 'name': row['name']} for row in system_rows if row['id'] in system_by_id],
        **_system_filter_options(system_rows),
    }


def build_bucket_detail(bucket_id: int) -> dict[str, Any] | None:
    bucket = (
        ObjectStorageBucket.query.options(
            joinedload(ObjectStorageBucket.object_storage_system).joinedload(ObjectStorageSystem.minio_connection)
        )
        .filter(ObjectStorageBucket.id == bucket_id)
        .first()
    )
    return _bucket_row(bucket) if bucket is not None else None
