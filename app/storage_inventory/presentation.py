from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.common.pagination import paginate_sequence
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem

OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS = 24

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


_RELEASE_TIMESTAMP_RE = re.compile(
    r'^RELEASE\.(?P<date>\d{4}-\d{2}-\d{2})T\d{2}-\d{2}-\d{2}Z$',
    re.IGNORECASE,
)
_PROFILE_RELEASE_RE = re.compile(
    r'^(?P<product>minio|astor)-release-(?P<date>\d{4}-\d{2}-\d{2})$',
    re.IGNORECASE,
)


def _release_display(value: str | None) -> str:
    """Return a compact operator-facing object-storage release label."""
    raw = str(value or '').strip()
    if not raw:
        return 'Not Declared'
    match = _RELEASE_TIMESTAMP_RE.fullmatch(raw)
    return match.group('date') if match else raw


def _compatibility_profile_display(value: str | None) -> str:
    """Convert compatibility profile keys into compact human-facing labels."""
    raw = str(value or '').strip()
    if not raw:
        return 'Not Resolved'
    match = _PROFILE_RELEASE_RE.fullmatch(raw)
    if match:
        product = 'MinIO' if match.group('product').lower() == 'minio' else 'AStor'
        release_date = match.group('date')
        return f'{product} {release_date}'
    return raw.replace('_', ' ').replace('-', ' ').title()


def _endpoint_display(value: str | None) -> str:
    """Return a compact endpoint label while preserving the full endpoint separately."""
    raw = str(value or '').strip()
    if not raw:
        return 'Not Configured'
    without_scheme = raw.split('://', 1)[-1]
    return without_scheme.split('/', 1)[0] or raw


def _product_label(value: str | None) -> str:
    key = str(value or '').strip().lower()
    return _PRODUCT_LABELS.get(key, key.replace('_', ' ').title() if key else 'Not Observed')


def _status(value: str | None) -> tuple[str, str]:
    key = str(value or 'unknown').strip().lower()
    return _STATUS_LABELS.get(key, (key.replace('_', ' ').title(), 'info'))


_NATIVE_TYPE_LABELS = {
    'bucket': 'Bucket',
    'container': 'Container',
}

_STATE_PRESENTATION = {
    'enabled': ('Enabled', 'normal'),
    'configured': ('Configured', 'normal'),
    'enforced': ('Enforced', 'normal'),
    'private': ('Private', 'normal'),
    'restricted': ('Restricted', 'info'),
    'disabled': ('Disabled', 'warning'),
    'suspended': ('Suspended', 'warning'),
    'not_configured': ('Not Configured', 'warning'),
    'public': ('Public', 'critical'),
    'not_collected': ('Not Assessed', 'unknown'),
    'not_supported': ('Not Supported', 'info'),
    'unknown': ('Unknown', 'unknown'),
    'collected': ('Collected', 'normal'),
}


def _format_bytes(value: int | None) -> str:
    if value is None:
        return 'Not Collected'
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    size = float(max(value, 0))
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f'{int(size)} B'
    return f'{size:.2f} {units[unit_index]}'


def _format_count(value: int | None) -> str:
    return 'Not Collected' if value is None else f'{max(value, 0):,}'


def _native_type_label(value: str | None) -> str:
    key = str(value or 'bucket').strip().lower().replace('-', '_')
    return _NATIVE_TYPE_LABELS.get(key, key.replace('_', ' ').title())


def _state_view(value: str | None) -> dict[str, str]:
    key = str(value or 'not_collected').strip().lower().replace('-', '_')
    label, tone = _STATE_PRESENTATION.get(key, (key.replace('_', ' ').title(), 'info'))
    return {'key': key, 'label': label, 'tone': tone}


def _protection_posture(
    *,
    versioning_state: str | None,
    immutability_state: str | None,
    encryption_state: str | None,
    exposure_state: str | None,
) -> dict[str, str]:
    exposure = _state_view(exposure_state)
    if exposure['key'] == 'public':
        return {'label': 'Attention', 'tone': 'critical'}

    states = [
        _state_view(versioning_state),
        _state_view(immutability_state),
        _state_view(encryption_state),
    ]
    observed = [state for state in states if state['key'] not in {'not_collected', 'not_supported', 'unknown'}]
    if not observed:
        return {'label': 'Not Assessed', 'tone': 'unknown'}

    positive = {'enabled', 'configured', 'enforced'}
    negative = {'disabled', 'suspended', 'not_configured'}
    if all(state['key'] in positive for state in observed) and len(observed) == len(states):
        return {'label': 'Protected', 'tone': 'normal'}
    if any(state['key'] in negative for state in observed):
        return {'label': 'Attention', 'tone': 'warning'}
    return {'label': 'Partial', 'tone': 'info'}


def _quota_view(quota_bytes: int | None, quota_state: str | None) -> dict[str, str]:
    key = str(quota_state or 'not_collected').strip().lower().replace('-', '_')
    if key == 'configured' and quota_bytes is not None:
        return {
            'key': 'configured',
            'label': _format_bytes(quota_bytes),
            'state_label': 'Configured',
            'tone': 'normal',
        }
    if key == 'not_configured':
        return {
            'key': key,
            'label': 'No Quota',
            'state_label': 'Not Configured',
            'tone': 'info',
        }
    if key == 'not_supported':
        return {
            'key': key,
            'label': 'Not Supported',
            'state_label': 'Not Supported',
            'tone': 'info',
        }
    return {
        'key': 'not_collected',
        'label': 'Not Collected',
        'state_label': 'Not Collected',
        'tone': 'unknown',
    }


def _collector_profile_label(metadata: dict[str, Any]) -> str:
    declared = str(metadata.get('enrichment_profile_label') or '').strip()
    if declared:
        return declared
    raw = str(metadata.get('enrichment_profile') or '').strip()
    return raw.replace('-', ' ').replace('_', ' ').title() if raw else 'Base Inventory'


def _usage_mode_label(metadata: dict[str, Any]) -> str:
    mode = str(metadata.get('usage_stats_mode') or 'disabled').strip().lower()
    return 'Full Scan' if mode == 'full_scan' else 'Disabled'


def _quota_collection_label(metadata: dict[str, Any]) -> str:
    source = str(metadata.get('quota_collection') or '').strip().lower()
    if source == 'minio-admin-v3':
        return 'MinIO Admin API v3'
    if source == 'not_supported':
        return 'Not Supported'
    return 'Not Collected'


def _provider_detail_sections(
    *,
    provider_metadata: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section in (provider_metadata or {}).get('sections', []):
        if not isinstance(section, dict):
            continue
        title = str(section.get('title') or '').strip()
        raw_rows = section.get('rows')
        if not title or not isinstance(raw_rows, list):
            continue
        rows: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict) or not raw_row.get('label'):
                continue
            value = raw_row.get('value')
            if value is None:
                continue
            if raw_row.get('value_type') == 'bytes':
                try:
                    value = _format_bytes(int(value))
                except (TypeError, ValueError):
                    value = 'Not Collected'
            rows.append(
                {
                    'label': str(raw_row.get('label')),
                    'value': value,
                    'technical': bool(raw_row.get('technical')),
                }
            )
        if rows:
            sections.append(
                {
                    'title': title,
                    'description': str(section.get('description') or 'Provider-specific inventory evidence.'),
                    'icon': str(section.get('icon') or 'braces'),
                    'rows': rows,
                }
            )
    return sections


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _is_stale(value: datetime | None, *, now: datetime | None = None) -> bool:
    observed = _aware(value)
    if observed is None:
        return False
    reference = _aware(now) or datetime.now(UTC)
    return reference - observed > timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS)


def _snapshot_status(value: datetime | None) -> tuple[str, str]:
    if value is None:
        return 'Not Collected', 'warning'
    if _is_stale(value):
        return 'Stale', 'warning'
    return 'Current', 'normal'


def _inventory_signals(row: dict[str, Any]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    if row['status_tone'] in {'critical', 'warning', 'unknown'}:
        signals.append(
            {
                'label': 'Provider Attention',
                'tone': 'critical' if row['status_tone'] == 'critical' else 'warning',
                'icon': 'triangle-alert',
                'description': 'Review provider readiness before relying on the next inventory refresh.',
            }
        )
    if row['last_inventory_at'] is None:
        signals.append(
            {
                'label': 'Inventory Not Collected',
                'tone': 'warning',
                'icon': 'database-zap',
                'description': 'Run Object Storage Inventory Sync from Job Execution to commit the first inventory snapshot.',
            }
        )
    elif _is_stale(row['last_inventory_at']):
        signals.append(
            {
                'label': 'Stale Snapshot',
                'tone': 'warning',
                'icon': 'clock-alert',
                'description': (
                    f'The committed inventory is older than {OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS} hours.'
                ),
            }
        )
    return signals


def _inventory_guidance(row: dict[str, Any], signals: list[dict[str, str]]) -> dict[str, str]:
    labels = {signal['label'] for signal in signals}
    if 'Provider Attention' in labels:
        return {
            'title': 'Review Provider Readiness',
            'description': 'Open the provider integration, resolve readiness issues with Full Validation, then run Inventory Sync.',
            'icon': 'triangle-alert',
            'tone': 'warning',
        }
    if 'Inventory Not Collected' in labels:
        return {
            'title': 'Collect Inventory',
            'description': 'Run Object Storage Inventory Sync from Job Execution to establish the first committed snapshot.',
            'icon': 'scan-search',
            'tone': 'warning',
        }
    if 'Stale Snapshot' in labels:
        return {
            'title': 'Refresh Inventory',
            'description': 'Run Object Storage Inventory Sync from Job Execution to refresh the committed snapshot.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    return {
        'title': 'No Action Required',
        'description': 'The committed object-storage inventory is current and has no active inventory signals.',
        'icon': 'circle-check',
        'tone': 'normal',
    }


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
    sync_status_label, sync_status_tone = _snapshot_status(latest_observed_at)
    row: dict[str, Any] = {
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
        'release_label': _release_display(connection.declared_release if connection is not None else None),
        'endpoint': connection.endpoint if connection is not None else 'Not Configured',
        'endpoint_display': _endpoint_display(connection.endpoint if connection is not None else None),
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
        'compatibility_profile_label': _compatibility_profile_display(
            connection.compatibility_profile if connection is not None else None
        ),
        'readiness_status': (
            connection.readiness_status
            if connection is not None and connection.readiness_status
            else 'validation_required'
        ),
        'bucket_count': len(buckets),
        'last_inventory_at': latest_observed_at,
        'sync_status_label': sync_status_label,
        'sync_status_tone': sync_status_tone,
        'snapshot_source': 'Committed Snapshot',
        'freshness_window_hours': OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS,
        'last_validated_at': connection.last_validated_at if connection is not None else None,
        'last_checked_at': connection.last_checked_at if connection is not None else None,
        'provider_connection_id': connection.id if connection is not None else None,
    }
    signals = _inventory_signals(row)
    row['signals'] = signals
    row['guidance'] = _inventory_guidance(row, signals)
    return row


def _system_filter_options(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    products = sorted({row['product_key'] for row in rows if row['product_key']})
    environments = sorted({str(row['environment']) for row in rows if row['environment']})
    statuses = sorted({str(row['status']) for row in rows if row['status']})
    return {
        'products': [{'value': value, 'label': _product_label(value)} for value in products],
        'environments': [{'value': value, 'label': value.title()} for value in environments],
        'statuses': [{'value': value, 'label': _status(value)[0]} for value in statuses],
    }


def _overview_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_systems = len(rows)
    inventoried = [row for row in rows if row['last_inventory_at'] is not None]
    latest = max((row['last_inventory_at'] for row in inventoried), default=None)
    missing_count = total_systems - len(inventoried)
    stale_count = sum(_is_stale(row['last_inventory_at']) for row in inventoried)
    provider_exception_count = sum(row['status_tone'] in {'critical', 'warning', 'unknown'} for row in rows)
    has_exceptions = bool(missing_count or stale_count or provider_exception_count)

    if total_systems == 0:
        status, tone = 'No Sources', 'unknown'
        description = 'Register a Storage integration to establish committed object-storage inventory.'
    elif has_exceptions:
        status, tone = 'Review Snapshot', 'warning'
        description = 'Committed inventory is available, with snapshot or provider conditions requiring review.'
    else:
        status, tone = 'Current', 'normal'
        description = 'All managed object-storage systems have current committed inventory.'

    exception_parts = [
        f'{count} {label}'
        for count, label in (
            (missing_count, 'Missing'),
            (stale_count, 'Stale'),
            (provider_exception_count, 'Provider'),
        )
        if count
    ]
    coverage_label = f'{len(inventoried)} / {total_systems} Systems' if total_systems else '0 / 0 Systems'
    coverage_supporting = (
        'Fully committed'
        if total_systems and len(inventoried) == total_systems
        else ('No committed data' if not inventoried else 'Partially committed')
    )
    return {
        'source_label': 'Committed Snapshot',
        'status': status,
        'tone': tone,
        'description': description,
        'latest_collected_at': latest,
        'latest_supporting': (
            f'{OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS}-hour freshness window' if latest else 'No committed timestamp'
        ),
        'scope_label': 'All Managed Systems',
        'scope_supporting': f'{total_systems} Systems Registered',
        'coverage_label': coverage_label,
        'coverage_supporting': coverage_supporting,
        'coverage_tone': (
            'normal'
            if total_systems and len(inventoried) == total_systems
            else ('unknown' if total_systems == 0 else 'warning')
        ),
        'exception_label': ' · '.join(exception_parts) if exception_parts else 'No Exceptions',
        'exceptions_supporting': 'Review required' if has_exceptions else 'No issues detected',
        'exceptions_tone': 'warning' if has_exceptions else 'normal',
    }


def _overview_asset_catalog(total_systems: int, total_buckets: int) -> list[dict[str, Any]]:
    return [
        {
            'title': 'Systems',
            'count': total_systems,
            'description': 'Managed object-storage systems.',
            'endpoint': 'object_storage_inventory.systems',
            'icon': 'server',
        },
        {
            'title': 'Buckets & Containers',
            'count': total_buckets,
            'description': 'Object-storage namespaces discovered from committed snapshots.',
            'endpoint': 'object_storage_inventory.buckets',
            'icon': 'container',
        },
    ]


def build_overview(*, system_page: int = 1, system_per_page: int = 5) -> dict[str, Any]:
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
    active_signal_count = sum(len(row['signals']) for row in rows)

    if total_systems == 0:
        posture_label, posture_tone = 'No Sources', 'unknown'
    elif blocked_systems or active_signal_count:
        posture_label, posture_tone = 'Attention Required', 'warning'
    elif inventoried_systems < total_systems:
        posture_label, posture_tone = 'Inventory Pending', 'warning'
    else:
        posture_label, posture_tone = 'Ready', 'normal'

    paged_rows, pagination = paginate_sequence(rows, page=system_page, per_page=system_per_page)
    return {
        'total_systems': total_systems,
        'total_buckets': total_buckets,
        'inventory_records': total_systems + total_buckets,
        'ready_systems': ready_systems,
        'blocked_systems': blocked_systems,
        'inventoried_systems': inventoried_systems,
        'inventory_coverage': coverage,
        'latest_inventory_at': latest_inventory_at,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'active_signal_count': active_signal_count,
        'asset_catalog': _overview_asset_catalog(total_systems, total_buckets),
        'snapshot': _overview_snapshot(rows),
        'systems': paged_rows,
        'systems_pagination': pagination,
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
    provider_key = str(connection.detected_product or '') if connection is not None else ''
    provider_label = _product_label(connection.detected_product if connection is not None else None)
    native_type = str(bucket.native_type or 'bucket').strip().lower()
    location = (
        str(bucket.location or '').strip() or (connection.region if connection is not None else '') or 'Not Observed'
    )
    addressing_style = (
        str(connection.addressing_style or 'path').replace('_', ' ').title()
        if connection is not None
        else 'Not Observed'
    )
    release_label = _release_display(connection.declared_release if connection is not None else None)
    compatibility_profile_label = _compatibility_profile_display(
        connection.compatibility_profile if connection is not None else None
    )
    endpoint = connection.endpoint if connection is not None else 'Not Configured'
    provider_metadata = dict(bucket.provider_metadata or {})
    versioning = _state_view(bucket.versioning_state)
    immutability = _state_view(bucket.immutability_state)
    encryption = _state_view(bucket.encryption_state)
    lifecycle = _state_view(bucket.lifecycle_state)
    replication = _state_view(bucket.replication_state)
    access_policy = _state_view(bucket.access_policy_state)
    exposure = _state_view(bucket.exposure_state)
    protection = _protection_posture(
        versioning_state=bucket.versioning_state,
        immutability_state=bucket.immutability_state,
        encryption_state=bucket.encryption_state,
        exposure_state=bucket.exposure_state,
    )
    quota = _quota_view(bucket.quota_bytes, bucket.quota_state)
    snapshot_status_label, snapshot_status_tone = _snapshot_status(bucket.observed_at)
    return {
        'id': bucket.id,
        'name': bucket.name,
        'system_id': system.id,
        'system_name': system.name,
        'environment': system.environment,
        'provider_key': provider_key,
        'provider_label': provider_label,
        # Compatibility aliases retained while downstream contracts move to provider terminology.
        'product_key': provider_key,
        'product_label': provider_label,
        'native_type': native_type,
        'native_type_label': _native_type_label(native_type),
        'location': location,
        'protection': protection,
        'versioning': versioning,
        'immutability': immutability,
        'encryption': encryption,
        'lifecycle': lifecycle,
        'replication': replication,
        'access_policy': access_policy,
        'exposure': exposure,
        'public_exposure': exposure,
        'size_bytes': bucket.size_bytes,
        'size_label': _format_bytes(bucket.size_bytes),
        'object_count': bucket.object_count,
        'object_count_label': _format_count(bucket.object_count),
        'usage_state': _state_view(bucket.usage_stats_state),
        'usage_observed_at': bucket.usage_observed_at,
        'provider_created_at': bucket.provider_created_at,
        'observed_at': bucket.observed_at,
        'snapshot_status_label': snapshot_status_label,
        'snapshot_status_tone': snapshot_status_tone,
        'snapshot_state': {'label': snapshot_status_label, 'tone': snapshot_status_tone},
        'region': connection.region if connection is not None else 'Not Observed',
        'endpoint': endpoint,
        'endpoint_display': _endpoint_display(endpoint),
        'addressing_style': addressing_style,
        'release_label': release_label,
        'compatibility_profile_label': compatibility_profile_label,
        'provider_connection_id': connection.id if connection is not None else None,
        'provider_metadata': provider_metadata,
        'enrichment_profile_label': _collector_profile_label(provider_metadata),
        'usage_stats_mode_label': _usage_mode_label(provider_metadata),
        'quota_collection_label': _quota_collection_label(provider_metadata),
        'enrichment_gaps': tuple(provider_metadata.get('enrichment_gaps') or ()),
        'quota_bytes': bucket.quota_bytes,
        'quota': quota,
        'quota_observed_at': bucket.quota_observed_at,
        'data_boundary': 'Latest committed Object Storage Inventory Sync snapshot; no live provider query is issued.',
        'recommended_action': (
            'Review optional admin:GetBucketQuota access when MinIO quota inventory is required.'
            if provider_key == 'minio' and quota['key'] == 'not_collected'
            else (
                'Review provider-specific enrichment when protection or access evidence is required.'
                if protection['label'] == 'Not Assessed'
                else 'Review normalized posture and provider-native evidence before making storage changes.'
            )
        ),
        'provider_detail_sections': _provider_detail_sections(
            provider_metadata=provider_metadata,
        ),
        'source_label': 'Committed Snapshot',
    }


@dataclass(frozen=True, slots=True)
class BucketFilters:
    search: str = ''
    system_id: str = ''
    product: str = ''
    native_type: str = ''
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
        if (
            not search
            or search
            in f'{row["name"]} {row["system_name"]} {row["provider_label"]} {row["native_type_label"]} {row["location"]}'.lower()
        )
        and (not filters.system_id or row['system_id'] == filters.system_id)
        and (not filters.product or row['provider_key'] == filters.product)
        and (not filters.native_type or row['native_type'] == filters.native_type)
        and (not filters.environment or row['environment'] == filters.environment)
    ]
    paged, pagination = paginate_sequence(filtered, page=filters.page, per_page=filters.per_page)
    bucket_count = sum(1 for row in filtered if row['native_type'] == 'bucket')
    container_count = sum(1 for row in filtered if row['native_type'] == 'container')
    return {
        'assets': paged,
        'buckets': paged,
        'pagination': pagination,
        'total_assets': len(filtered),
        'total_buckets': bucket_count,
        'total_containers': container_count,
        'systems_in_scope': len({row['system_id'] for row in filtered}),
        'providers_in_scope': len({row['provider_key'] for row in filtered if row['provider_key']}),
        'products_in_scope': len({row['provider_key'] for row in filtered if row['provider_key']}),
        'types': [
            {'value': value, 'label': _native_type_label(value)}
            for value in sorted({row['native_type'] for row in rows if row['native_type']})
        ],
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
