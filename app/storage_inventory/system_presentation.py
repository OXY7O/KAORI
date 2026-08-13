from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.models.object_storage import ObjectStorageSystem

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
