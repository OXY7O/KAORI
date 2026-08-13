from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import joinedload, selectinload

from app.common.pagination import paginate_sequence
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
from app.storage_inventory.system_presentation import (
    _compatibility_profile_display,
    _product_label,
    _release_display,
    _snapshot_status,
    _system_filter_options,
)
from app.storage_inventory.system_presentation import _endpoint_display as _system_endpoint_display
from app.storage_inventory.system_presentation import _inventory_guidance as _inventory_guidance
from app.storage_inventory.system_presentation import _inventory_signals as _inventory_signals
from app.storage_inventory.system_presentation import _is_stale as _is_stale
from app.storage_inventory.system_presentation import _overview_snapshot as _overview_snapshot_impl
from app.storage_inventory.system_presentation import _status as _status
from app.storage_inventory.system_presentation import _system_row as _system_row_impl

_NATIVE_TYPE_LABELS = {
    'bucket': 'Bucket',
    'container': 'Container',
}

_SYSTEM_SNAPSHOT_SOURCE = {'snapshot_source': 'Committed Snapshot'}
OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS = 24
_OVERVIEW_SIGNAL_LABELS = ('Inventory Not Collected', 'Stale Snapshot', 'Provider Attention')


class _BucketPostureSource(Protocol):
    quota_state: str
    versioning_state: str
    immutability_state: str
    encryption_state: str
    exposure_state: str
    usage_stats_state: str


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


def _endpoint_display(value: str | None) -> str:
    return _system_endpoint_display(value)


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
    versioning_state: str,
    immutability_state: str,
    encryption_state: str,
    exposure_state: str,
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
    if mode == 'provider_metrics':
        return 'Provider Metrics'
    if mode == 'full_scan':
        return 'Full Scan'
    return 'Disabled'


def _usage_collection_label(metadata: dict[str, Any]) -> str:
    source = str(metadata.get('usage_collection') or '').strip().lower()
    if source == 'minio_admin_data_usage_v3':
        return 'MinIO Admin Data Usage v3'
    if source == 'minio_admin_data_usage_v4':
        return 'MinIO Admin Data Usage v4'
    if source == 's3_list_objects_v2':
        return 'S3 ListObjectsV2'
    if source == 'disabled':
        return 'Disabled'
    return 'Not Observed'


def _quota_collection_label(source: str | None, metadata: dict[str, Any]) -> str:
    resolved = str(source or metadata.get('quota_collection') or '').strip().lower()
    if resolved == 'minio_admin_api_v3':
        return 'MinIO Admin API v3'
    if resolved == 'minio_admin_api_v4':
        return 'MinIO Admin API v4'
    if resolved == 'not_supported':
        return 'Not Supported'
    return 'Not Observed'


_QUOTA_EVIDENCE_PRESENTATION: dict[str, tuple[str, str, str]] = {
    'collected': (
        'Collected',
        'normal',
        'Bucket quota was collected successfully from the provider Admin API.',
    ),
    'not_configured': (
        'No Quota Configured',
        'info',
        'The provider returned no configured bucket-level quota ceiling.',
    ),
    'access_denied': (
        'Access Denied',
        'warning',
        'Grant the inventory credential admin:GetBucketQuota access, then run Object Storage Inventory Sync again.',
    ),
    'invalid_credentials': (
        'Invalid Credentials',
        'critical',
        'Verify the configured MinIO access key and secret key before retrying quota collection.',
    ),
    'signature_mismatch': (
        'Signature Mismatch',
        'warning',
        'Verify endpoint routing, request signing, proxy rewriting, and the configured MinIO region.',
    ),
    'admin_api_unreachable': (
        'Admin API Unreachable',
        'warning',
        'Verify that the MinIO API endpoint and reverse proxy allow /minio/admin/* requests from the inventory worker.',
    ),
    'admin_api_timeout': (
        'Admin API Timeout',
        'warning',
        'The provider Admin API did not respond before the inventory timeout. '
        'Review provider health and network latency.',
    ),
    'tls_validation_failed': (
        'TLS Validation Failed',
        'critical',
        'Verify the certificate chain presented by the MinIO API endpoint before retrying quota collection.',
    ),
    'rate_limited': (
        'Rate Limited',
        'warning',
        'The provider throttled quota collection. Retry later or reduce inventory concurrency.',
    ),
    'invalid_response': (
        'Invalid Admin API Response',
        'warning',
        'The Admin API responded but did not return a valid bucket quota payload. Review provider compatibility.',
    ),
    'provider_error': (
        'Provider Error',
        'warning',
        'The MinIO Admin API returned an unexpected provider error. '
        'Review provider health and retry the inventory job.',
    ),
    'invalid_endpoint': (
        'Invalid Endpoint',
        'critical',
        'Correct the configured MinIO API endpoint before running object-storage inventory again.',
    ),
    'not_supported': (
        'Not Supported',
        'info',
        'The provider Admin API generation required for quota collection is not available through this endpoint.',
    ),
    'not_collected': (
        'Not Collected',
        'unknown',
        'Quota evidence was not collected during the latest inventory snapshot.',
    ),
}


def _quota_evidence_view(
    evidence_code: str | None,
    *,
    quota_state: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    key = str(evidence_code or '').strip().lower().replace('-', '_')
    if not key:
        state = str(quota_state or '').strip().lower().replace('-', '_')
        key = 'collected' if state == 'configured' else state or 'not_collected'
    label, tone, guidance = _QUOTA_EVIDENCE_PRESENTATION.get(
        key,
        _QUOTA_EVIDENCE_PRESENTATION['not_collected'],
    )
    raw = metadata.get('quota_evidence') if isinstance(metadata, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    status_code = raw.get('status_code')
    provider_code = str(raw.get('provider_code') or '').strip()
    supporting_parts: list[str] = []
    if status_code:
        supporting_parts.append(f'HTTP {status_code}')
    if provider_code:
        supporting_parts.append(provider_code)
    return {
        'key': key,
        'label': label,
        'tone': tone,
        'guidance': guidance,
        'supporting': ' · '.join(supporting_parts),
    }


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


def _system_query():
    return ObjectStorageSystem.query.options(
        joinedload(ObjectStorageSystem.minio_connection),
        selectinload(ObjectStorageSystem.buckets),
    ).order_by(ObjectStorageSystem.name.asc())


def _system_row(system: ObjectStorageSystem) -> dict[str, Any]:
    """Committed row used by inventory pages. Run Object Storage Inventory Sync from Job Execution."""
    row = _system_row_impl(system)
    connection = system.minio_connection
    row.update(
        {
            'release_label': _release_display(connection.declared_release if connection is not None else None),
            'compatibility_profile_label': _compatibility_profile_display(
                connection.compatibility_profile if connection is not None else None
            ),
            **_SYSTEM_SNAPSHOT_SOURCE,
        }
    )
    return row


def _overview_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Canonical labels stay owned by this presentation boundary; calculation is delegated.
    _ = _OVERVIEW_SIGNAL_LABELS
    return _overview_snapshot_impl(rows)


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


def _overview_bucket_posture(buckets: Sequence[_BucketPostureSource]) -> dict[str, Any]:
    total = len(buckets)
    quota_assessed = quota_configured = protection_attention = public_exposure = usage_collected = 0
    for bucket in buckets:
        quota_key = str(bucket.quota_state or 'not_collected').strip().lower().replace('-', '_')
        quota_assessed += int(quota_key in {'configured', 'not_configured'})
        quota_configured += int(quota_key == 'configured')
        protection = _protection_posture(
            versioning_state=bucket.versioning_state,
            immutability_state=bucket.immutability_state,
            encryption_state=bucket.encryption_state,
            exposure_state=bucket.exposure_state,
        )
        protection_attention += int(protection['tone'] in {'warning', 'critical'})
        public_exposure += int(str(bucket.exposure_state or '').strip().lower() == 'public')
        usage_collected += int(str(bucket.usage_stats_state or '').strip().lower() == 'collected')
    return {
        'total_assets': total,
        'quota_assessed': quota_assessed,
        'quota_configured': quota_configured,
        'quota_gaps': max(total - quota_assessed, 0),
        'protection_attention': protection_attention,
        'public_exposure': public_exposure,
        'usage_collected': usage_collected,
    }


def _overview_fleet_readings(posture: dict[str, Any]) -> list[dict[str, str]]:
    total = int(posture['total_assets'])
    quota_assessed = int(posture['quota_assessed'])
    quota_configured = int(posture['quota_configured'])
    quota_gaps = int(posture['quota_gaps'])
    protection_attention = int(posture['protection_attention'])
    public_exposure = int(posture['public_exposure'])
    usage_collected = int(posture['usage_collected'])
    if total == 0:
        quota_title, quota_tone = 'No Quota Evidence', 'unknown'
        quota_description = 'No committed bucket or container assets are available yet.'
    elif quota_gaps:
        quota_title, quota_tone = f'{quota_assessed}/{total} Quota Assessed', 'warning'
        quota_description = (
            f'{quota_configured} asset(s) have configured quota; {quota_gaps} still require provider evidence.'
        )
    else:
        quota_title, quota_tone = f'{quota_assessed}/{total} Quota Assessed', 'normal'
        quota_description = f'Quota evidence is complete; {quota_configured} asset(s) have a configured quota ceiling.'
    return [
        {'title': quota_title, 'description': quota_description, 'icon': 'gauge', 'tone': quota_tone},
        {
            'title': f'{protection_attention} Protection Attention'
            if protection_attention
            else 'No Protection Attention',
            'description': (
                'Review versioning, encryption, immutability, and exposure posture for the affected assets.'
                if protection_attention
                else 'No committed bucket or container currently requires normalized protection review.'
            ),
            'icon': 'shield-check',
            'tone': 'warning' if protection_attention else 'normal',
        },
        {
            'title': f'{public_exposure} Public Exposure' if public_exposure else 'No Public Exposure',
            'description': (
                'Review provider access policy evidence for publicly exposed assets.'
                if public_exposure
                else 'No committed asset is currently classified as public.'
            ),
            'icon': 'key-round',
            'tone': 'critical' if public_exposure else 'normal',
        },
        {
            'title': f'{usage_collected}/{total} Usage Collected' if total else 'No Usage Evidence',
            'description': (
                'Used size and current object count are optional inventory evidence collected by the configured usage strategy.'
                if total
                else 'No committed bucket or container assets are available for usage collection.'
            ),
            'icon': 'chart-no-axes-column',
            'tone': 'info',
        },
    ]


def _overview_provider_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get('product_label') or 'Not Observed')
        counts[label] = counts.get(label, 0) + 1
    return [
        {'label': label, 'count': count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_overview(*, system_page: int = 1, system_per_page: int = 5) -> dict[str, Any]:
    rows = [_system_row(system) for system in _system_query().all()]
    buckets = ObjectStorageBucket.query.all()
    total_systems, total_buckets = len(rows), len(buckets)
    bucket_posture = _overview_bucket_posture(buckets)
    ready_systems = sum(1 for row in rows if row['status_tone'] == 'normal')
    blocked_systems = sum(1 for row in rows if row['status_tone'] == 'critical')
    inventoried_systems = sum(1 for row in rows if row['last_inventory_at'] is not None)
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
    latest_inventory_at = max((row['last_inventory_at'] for row in rows if row['last_inventory_at']), default=None)
    return {
        'total_systems': total_systems,
        'total_buckets': total_buckets,
        'inventory_records': total_systems + total_buckets,
        'ready_systems': ready_systems,
        'blocked_systems': blocked_systems,
        'inventoried_systems': inventoried_systems,
        'inventory_coverage': round((inventoried_systems / total_systems) * 100) if total_systems else 0,
        'latest_inventory_at': latest_inventory_at,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'active_signal_count': active_signal_count,
        'asset_catalog': _overview_asset_catalog(total_systems, total_buckets),
        'bucket_posture': bucket_posture,
        'fleet_readings': _overview_fleet_readings(bucket_posture),
        'provider_distribution': _overview_provider_distribution(rows),
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
        'usage_collection_label': _usage_collection_label(provider_metadata),
        'quota_collection_label': _quota_collection_label(bucket.quota_source, provider_metadata),
        'quota_evidence': _quota_evidence_view(
            bucket.quota_evidence_code,
            quota_state=bucket.quota_state,
            metadata=provider_metadata,
        ),
        'enrichment_gaps': tuple(provider_metadata.get('enrichment_gaps') or ()),
        'quota_bytes': bucket.quota_bytes,
        'quota': quota,
        'quota_source': bucket.quota_source,
        'quota_checked_at': bucket.quota_checked_at,
        'quota_observed_at': bucket.quota_observed_at,
        'data_boundary': 'Latest committed Object Storage Inventory Sync snapshot; no live provider query is issued.',
        'recommended_action': (
            _quota_evidence_view(
                bucket.quota_evidence_code,
                quota_state=bucket.quota_state,
                metadata=provider_metadata,
            )['guidance']
            if provider_key == 'minio' and quota['key'] in {'not_collected', 'not_supported'}
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


def _bucket_matches_filters(row: dict[str, Any], filters: BucketFilters, search: str) -> bool:
    searchable = (
        f'{row["name"]} {row["system_name"]} {row["provider_label"]} {row["native_type_label"]} {row["location"]}'
    ).lower()
    return (
        (not search or search in searchable)
        and (not filters.system_id or row['system_id'] == filters.system_id)
        and (not filters.product or row['provider_key'] == filters.product)
        and (not filters.native_type or row['native_type'] == filters.native_type)
        and (not filters.environment or row['environment'] == filters.environment)
    )


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
    filtered = [row for row in rows if _bucket_matches_filters(row, filters, search)]
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
