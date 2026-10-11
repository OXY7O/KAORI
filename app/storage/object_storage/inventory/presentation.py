from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import case, func
from sqlalchemy.orm import aliased, joinedload, selectinload

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.integrations.managed_assets import ManagedAssetOwner, object_storage_owner
from app.integrations.provider_matrix import provider_kinds
from app.models.integration import IntegrationInstance
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
from app.storage.object_storage.inventory.aggregates import bucket_fleet_posture
from app.storage.object_storage.inventory.system_presentation import (
    _compatibility_profile_display,
    _overview_snapshot_from_counts,
    _release_display,
    _snapshot_status,
)
from app.storage.object_storage.inventory.system_presentation import _endpoint_display as _system_endpoint_display
from app.storage.object_storage.inventory.system_presentation import _inventory_guidance as _inventory_guidance
from app.storage.object_storage.inventory.system_presentation import _inventory_signals as _inventory_signals
from app.storage.object_storage.inventory.system_presentation import _is_stale as _is_stale
from app.storage.object_storage.inventory.system_presentation import _overview_snapshot as _overview_snapshot_impl
from app.storage.object_storage.inventory.system_presentation import _provider_label as _provider_label
from app.storage.object_storage.inventory.system_presentation import _status as _status
from app.storage.object_storage.inventory.system_presentation import _system_row as _system_row_impl

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
    return ObjectStorageSystem.query.options(selectinload(ObjectStorageSystem.buckets)).order_by(
        ObjectStorageSystem.name.asc()
    )


def _system_row(system: ObjectStorageSystem) -> dict[str, Any]:
    """Committed row used by inventory pages. Run Object Storage Inventory Sync from Job Execution."""
    owner = object_storage_owner(system.id)
    row = _system_row_impl(system, owner=owner, owner_resolved=True)
    connection = owner.record if owner is not None else None
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


def _setup_state(total_systems: int) -> dict[str, Any]:
    return {
        'is_blocked': total_systems == 0,
        'registered_systems': total_systems,
        'state': 'setup_required' if total_systems == 0 else 'available',
    }


def _overview_asset_catalog(total_systems: int, total_buckets: int) -> list[dict[str, Any]]:
    return [
        {
            'title': 'Systems',
            'count': total_systems,
            'description': 'Open system identity, provider readiness, endpoint, release, and committed snapshot details.',
            'endpoint': 'object_storage_inventory.systems',
            'icon': 'server',
            'action_label': 'Browse Systems',
        },
        {
            'title': 'Buckets & Containers',
            'count': total_buckets,
            'description': 'Open bucket and container protection, capacity, lifecycle, access, and usage evidence.',
            'endpoint': 'object_storage_inventory.buckets',
            'icon': 'container',
            'action_label': 'Browse Buckets & Containers',
        },
    ]


def _overview_bucket_posture(buckets: Sequence[_BucketPostureSource]) -> dict[str, Any]:
    total = len(buckets)
    quota_assessed = quota_configured = protection_attention = public_exposure = usage_collected = 0
    protection_assessed = exposure_assessed = 0
    known_protection_states = {'enabled', 'configured', 'enforced', 'disabled', 'suspended', 'not_configured'}
    classified_exposure_states = {'public', 'private', 'restricted'}
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
        protection_states = (
            _state_view(bucket.versioning_state)['key'],
            _state_view(bucket.immutability_state)['key'],
            _state_view(bucket.encryption_state)['key'],
        )
        protection_assessed += int(all(state in known_protection_states for state in protection_states))
        exposure_key = _state_view(bucket.exposure_state)['key']
        exposure_assessed += int(exposure_key in classified_exposure_states)
        public_exposure += int(exposure_key == 'public')
        usage_collected += int(str(bucket.usage_stats_state or '').strip().lower() == 'collected')
    return {
        'total_assets': total,
        'quota_assessed': quota_assessed,
        'quota_configured': quota_configured,
        'quota_gaps': max(total - quota_assessed, 0),
        'protection_attention': protection_attention,
        'protection_assessed': protection_assessed,
        'public_exposure': public_exposure,
        'exposure_assessed': exposure_assessed,
        'usage_collected': usage_collected,
    }


def _overview_fleet_readings(posture: dict[str, Any]) -> list[dict[str, str]]:
    total = int(posture['total_assets'])
    quota_assessed = int(posture['quota_assessed'])
    quota_configured = int(posture['quota_configured'])
    quota_gaps = int(posture['quota_gaps'])
    protection_attention = int(posture['protection_attention'])
    protection_assessed = int(posture['protection_assessed'])
    public_exposure = int(posture['public_exposure'])
    exposure_assessed = int(posture['exposure_assessed'])
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

    if total == 0:
        protection_title, protection_tone = 'No Protection Evidence', 'unknown'
        protection_description = 'No committed bucket or container assets are available yet.'
    elif protection_attention:
        protection_title, protection_tone = f'{protection_attention} Protection Attention', 'warning'
        protection_description = (
            f'Review flagged controls; complete protection evidence exists for {protection_assessed}/{total} assets.'
        )
    elif protection_assessed < total:
        protection_title = 'Protection Not Assessed' if protection_assessed == 0 else 'Protection Partially Assessed'
        protection_tone = 'unknown' if protection_assessed == 0 else 'warning'
        protection_description = (
            f'No attention observed, but complete protection evidence exists for only {protection_assessed}/{total} assets.'
        )
    else:
        protection_title, protection_tone = 'No Protection Attention', 'normal'
        protection_description = 'All committed assets have assessed versioning, encryption, and immutability evidence.'

    if total == 0:
        exposure_title, exposure_tone = 'No Exposure Evidence', 'unknown'
        exposure_description = 'No committed bucket or container assets are available yet.'
    elif public_exposure:
        exposure_title, exposure_tone = f'{public_exposure} Public Exposure', 'critical'
        exposure_description = (
            f'Review provider access policy evidence for publicly exposed assets; '
            f'exposure is classified for {exposure_assessed}/{total} assets.'
        )
    elif exposure_assessed < total:
        exposure_title = 'Exposure Not Assessed' if exposure_assessed == 0 else 'Exposure Partially Assessed'
        exposure_tone = 'unknown' if exposure_assessed == 0 else 'warning'
        exposure_description = (
            f'No public exposure observed; classification evidence exists for only {exposure_assessed}/{total} assets.'
        )
    else:
        exposure_title, exposure_tone = 'No Public Exposure', 'normal'
        exposure_description = (
            'No committed asset is currently classified as public in the latest Object Storage inventory evidence.'
        )

    return [
        {'title': quota_title, 'description': quota_description, 'icon': 'gauge', 'tone': quota_tone},
        {
            'title': protection_title,
            'description': protection_description,
            'icon': 'shield-check',
            'tone': protection_tone,
        },
        {
            'title': exposure_title,
            'description': exposure_description,
            'icon': 'key-round',
            'tone': exposure_tone,
        },
        {
            'title': f'{usage_collected}/{total} Usage Collected' if total else 'No Usage Evidence',
            'description': (
                'Used size and object count are optional usage evidence.'
                if total
                else 'No committed bucket or container assets are available for usage collection.'
            ),
            'icon': 'chart-no-axes-column',
            'tone': 'info',
        },
    ]


def _overview_fleet_posture_metrics(
    posture: dict[str, Any],
    readings: Sequence[dict[str, str]],
) -> list[tuple[str, str, str, str, str]]:
    """Project committed fleet readings into the canonical grouped metric layout."""
    total = int(posture['total_assets'])
    metric_values = (
        ('Quota Assessed', f"{posture['quota_assessed']}/{total}" if total else 'No Evidence'),
        (
            'Protection Attention',
            str(posture['protection_attention']) if posture['protection_assessed'] else 'No Evidence',
        ),
        (
            'Public Exposure',
            str(posture['public_exposure']) if posture['exposure_assessed'] else 'No Evidence',
        ),
        ('Usage Collected', f"{posture['usage_collected']}/{total}" if total else 'No Evidence'),
    )
    return [
        (reading['icon'], label, value, reading['description'], reading['tone'])
        for reading, (label, value) in zip(readings, metric_values, strict=True)
    ]


def _overview_provider_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get('provider_label') or 'Not Observed')
        counts[label] = counts.get(label, 0) + 1
    return [
        {'label': label, 'count': count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_overview() -> dict[str, Any]:
    """Project exact committed fleet evidence using bounded SQL aggregates."""
    threshold = datetime.now(UTC) - timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS)
    status = func.lower(func.trim(func.coalesce(ObjectStorageSystem.status, 'unknown')))
    normal = status.in_(('ready', 'connected'))
    critical = status.in_(('blocked', 'failed'))
    provider_attention = status.in_(('blocked', 'failed', 'warning', 'unknown'))
    (total, observed, ready, blocked, attention, stale, latest) = (
        db.session.query(
            func.count(ObjectStorageSystem.id),
            func.count(ObjectStorageSystem.inventory_observed_at),
            func.sum(case((normal, 1), else_=0)),
            func.sum(case((critical, 1), else_=0)),
            func.sum(case((provider_attention, 1), else_=0)),
            func.sum(case((
                ObjectStorageSystem.inventory_observed_at < threshold, 1
            ), else_=0)),
            func.max(ObjectStorageSystem.inventory_observed_at),
        )
        .one()
    )
    total_systems, inventoried_systems = int(total or 0), int(observed or 0)
    ready_systems, blocked_systems = int(ready or 0), int(blocked or 0)
    provider_attention_count, stale_count = int(attention or 0), int(stale or 0)
    missing_count = total_systems - inventoried_systems
    active_signal_count = provider_attention_count + stale_count + missing_count

    bucket_posture = bucket_fleet_posture()
    total_buckets = bucket_posture['total_assets']
    fleet_readings = _overview_fleet_readings(bucket_posture)

    # Provider distribution uses the same authoritative canonical-owner join as list pages.
    owner_query = _system_scope().order_by(None)
    provider_label = _sql_provider_label()
    distributions = owner_query.with_entities(
        provider_label.label('provider_label'),
        func.count(ObjectStorageSystem.id).label('system_count'),
    ).group_by(provider_label).all()
    provider_distribution = [
        {'label': label, 'count': int(count)}
        for label, count in sorted(distributions, key=lambda row: (-row[1], row[0]))
    ]
    if total_systems == 0:
        posture_label, posture_tone = 'No Sources', 'unknown'
    elif blocked_systems or active_signal_count:
        posture_label, posture_tone = 'Attention Required', 'warning'
    elif inventoried_systems < total_systems:
        posture_label, posture_tone = 'Inventory Pending', 'warning'
    else:
        posture_label, posture_tone = 'Ready', 'normal'

    return {
        'total_systems': total_systems,
        'total_buckets': total_buckets,
        'inventory_records': total_systems + total_buckets,
        'ready_systems': ready_systems,
        'blocked_systems': blocked_systems,
        'inventoried_systems': inventoried_systems,
        'inventory_coverage': round((inventoried_systems / total_systems) * 100) if total_systems else 0,
        'latest_inventory_at': latest,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'active_signal_count': active_signal_count,
        'asset_catalog': _overview_asset_catalog(total_systems, total_buckets),
        'bucket_posture': bucket_posture,
        'fleet_readings': fleet_readings,
        'fleet_posture_metrics': _overview_fleet_posture_metrics(bucket_posture, fleet_readings),
        'provider_distribution': provider_distribution,
        'setup': _setup_state(total_systems),
        'snapshot': _overview_snapshot_from_counts(
            total_systems=total_systems,
            inventoried_count=inventoried_systems,
            latest=latest,
            missing_count=missing_count,
            stale_count=stale_count,
            provider_exception_count=provider_attention_count,
        ),
    }


@dataclass(frozen=True, slots=True)
class SystemFilters:
    search: str = ''
    provider: str = ''
    environment: str = ''
    status: str = ''
    page: int = 1
    per_page: int = 5


def _join_system_owner(query):
    """Join the first canonical integration owner once, without N+1 record lookups."""
    identity = aliased(IntegrationInstance)
    owner_ids = (
        db.session.query(
            identity.metadata_json['asset_key'].as_string().label('asset_key'),
            func.min(identity.id).label('owner_id'),
        )
        .filter(
            identity.integration_type == 'object_storage',
            identity.metadata_json['asset_type'].as_string() == 'object_storage_system',
        )
        .group_by(identity.metadata_json['asset_key'].as_string())
        .subquery()
    )
    return (
        query.outerjoin(owner_ids, owner_ids.c.asset_key == ObjectStorageSystem.id)
        .outerjoin(IntegrationInstance, IntegrationInstance.id == owner_ids.c.owner_id)
        .outerjoin(MinioInstance, MinioInstance.integration_instance_id == IntegrationInstance.id)
    )


def _system_scope():
    return _join_system_owner(ObjectStorageSystem.query)


def _sql_provider_label():
    options = provider_kinds('object_storage')
    when = [(IntegrationInstance.provider_key == option.key, option.label) for option in options]
    return case(*when, else_='Object Storage')


def _system_options() -> dict[str, list[dict[str, str]]]:
    """Return only distinct scalar filter values, never full system/bucket rows."""
    source = _system_scope()
    providers = {
        value for (value,) in source.with_entities(IntegrationInstance.provider_key)
        .distinct().all() if value
    }
    environments = {
        value for (value,) in source.with_entities(ObjectStorageSystem.environment)
        .distinct().all() if value
    }
    statuses = {
        value for (value,) in source.with_entities(ObjectStorageSystem.status)
        .distinct().all() if value
    }
    return {
        'providers': [
            {'value': key, 'label': _provider_label(key)} for key in sorted(providers)
        ],
        'environments': [
            {'value': value, 'label': value.title()} for value in sorted(environments)
        ],
        'statuses': [
            {'value': value, 'label': _status(value)[0]} for value in sorted(statuses)
        ],
    }


def _committed_system_snapshot() -> dict[str, Any]:
    """Exact fleet counts/status from SQL, with shared committed snapshot copy."""
    threshold = datetime.now(UTC) - timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS)
    total, observed, latest, stale, exceptions = db.session.query(
        func.count(ObjectStorageSystem.id),
        func.count(ObjectStorageSystem.inventory_observed_at),
        func.max(ObjectStorageSystem.inventory_observed_at),
        func.sum(case((ObjectStorageSystem.inventory_observed_at < threshold, 1), else_=0)),
        func.sum(case((
            func.lower(ObjectStorageSystem.status).in_(
                ('blocked', 'failed', 'warning', 'unknown')
            ), 1
        ), else_=0)),
    ).one()
    total_count, observed_count = int(total or 0), int(observed or 0)
    return _overview_snapshot_from_counts(
        total_systems=total_count,
        inventoried_count=observed_count,
        latest=latest,
        missing_count=total_count - observed_count,
        stale_count=int(stale or 0),
        provider_exception_count=int(exceptions or 0),
    )


def _filtered_systems(filters: SystemFilters):
    query = _system_scope()
    search = filters.search.strip().lower()
    if search:
        searchable = func.lower(
            func.coalesce(ObjectStorageSystem.name, '') + ' '
            + func.coalesce(MinioInstance.endpoint, 'Not Configured') + ' '
            + _sql_provider_label()
        )
        query = query.filter(searchable.contains(search, autoescape=True))
    if filters.provider:
        query = query.filter(IntegrationInstance.provider_key == filters.provider)
    if filters.environment:
        query = query.filter(ObjectStorageSystem.environment == filters.environment)
    if filters.status:
        query = query.filter(ObjectStorageSystem.status == filters.status)
    return query.order_by(ObjectStorageSystem.name.asc(), ObjectStorageSystem.id.asc())


def build_systems(filters: SystemFilters) -> dict[str, Any]:
    query = _filtered_systems(filters)
    total, ready, blocked, attention, inventoried = query.order_by(None).with_entities(
        func.count(ObjectStorageSystem.id),
        func.sum(case((
            func.lower(ObjectStorageSystem.status).in_(('ready', 'connected')), 1
        ), else_=0)),
        func.sum(case((
            func.lower(ObjectStorageSystem.status).in_(('blocked', 'failed')), 1
        ), else_=0)),
        func.sum(case((
            func.lower(ObjectStorageSystem.status).in_(
                ('blocked', 'failed', 'warning', 'unknown')
            ), 1
        ), else_=0)),
        func.count(ObjectStorageSystem.inventory_observed_at),
    ).one()
    paged, pagination = paginate_query(
        query.options(selectinload(ObjectStorageSystem.buckets)),
        page=filters.page,
        per_page=filters.per_page,
    )
    return {
        'systems': [_system_row(system) for system in paged],
        'pagination': pagination,
        'total_systems': int(total or 0),
        'ready_systems': int(ready or 0),
        'blocked_systems': int(blocked or 0),
        'attention_systems': int(attention or 0),
        'inventoried_systems': int(inventoried or 0),
        'setup': _setup_state(ObjectStorageSystem.query.count()),
        'snapshot': _committed_system_snapshot(),
        **_system_options(),
    }


def build_system_detail(system_id: str) -> dict[str, Any] | None:
    system = _system_query().filter(ObjectStorageSystem.id == system_id).first()
    return _system_row(system) if system is not None else None


def _bucket_row(
    bucket: ObjectStorageBucket, *, owner_cache: dict[str, ManagedAssetOwner | None] | None = None
) -> dict[str, Any]:
    system = bucket.object_storage_system
    if owner_cache is not None and str(system.id) in owner_cache:
        owner = owner_cache[str(system.id)]
    else:
        owner = object_storage_owner(system.id)
        if owner_cache is not None:
            owner_cache[str(system.id)] = owner
    connection = owner.record if owner is not None else None
    provider_key = owner.provider_key if owner is not None else ''
    provider_label = owner.provider.label if owner is not None else 'Object Storage'
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
        'data_boundary': 'Latest committed Inventory Sync snapshot; no live provider query.',
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
    provider: str = ''
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
        and (not filters.provider or row['provider_key'] == filters.provider)
        and (not filters.native_type or row['native_type'] == filters.native_type)
        and (not filters.environment or row['environment'] == filters.environment)
    )


def _filtered_buckets(filters: BucketFilters):
    query = _join_system_owner(
        ObjectStorageBucket.query.join(
            ObjectStorageSystem,
            ObjectStorageBucket.object_storage_system_id == ObjectStorageSystem.id,
        )
    )
    search = filters.search.strip().lower()
    if search:
        location = func.coalesce(
            func.nullif(ObjectStorageBucket.location, ''),
            MinioInstance.region,
            'Not Observed',
        )
        searchable = func.lower(
            ObjectStorageBucket.name + ' ' + ObjectStorageSystem.name + ' '
            + _sql_provider_label() + ' '
            + func.coalesce(ObjectStorageBucket.native_type, 'bucket') + ' ' + location
        )
        query = query.filter(searchable.contains(search, autoescape=True))
    if filters.system_id:
        query = query.filter(ObjectStorageBucket.object_storage_system_id == filters.system_id)
    if filters.provider:
        query = query.filter(IntegrationInstance.provider_key == filters.provider)
    if filters.native_type:
        query = query.filter(ObjectStorageBucket.native_type == filters.native_type)
    if filters.environment:
        query = query.filter(ObjectStorageSystem.environment == filters.environment)
    return query.order_by(ObjectStorageBucket.name.asc(), ObjectStorageBucket.id.asc())



def _bucket_empty_state(total_committed_assets: int, snapshot: dict[str, Any]) -> dict[str, str]:
    """Distinguish missing evidence from a legitimate empty committed collection."""
    if total_committed_assets:
        return {
            'label': 'No Matches',
            'title': 'No Buckets or Containers Match These Filters',
            'description': 'Adjust the active search or filters to review committed bucket and container inventory.',
            'icon': 'search-x',
        }
    if snapshot.get('latest_collected_at') is None:
        return {
            'label': 'Collection Pending',
            'title': 'No Buckets or Containers Collected Yet',
            'description': 'Run Object Storage Inventory Sync from Job Execution after the registered provider is Ready.',
            'icon': 'database-zap',
        }
    if snapshot.get('coverage_tone') != 'normal':
        return {
            'label': 'Partial Inventory',
            'title': 'No Buckets or Containers in Collected Systems',
            'description': (
                'Some systems have committed empty inventory; other systems still need collection. '
                'Review the Inventory Data Snapshot coverage before interpreting the fleet.'
            ),
            'icon': 'database-zap',
        }
    return {
        'label': 'Observed Empty',
        'title': 'No Buckets or Containers Observed',
        'description': (
            'The last committed Inventory Sync successfully observed zero buckets or containers '
            'across all registered systems. This is not a live provider check.'
        ),
        'icon': 'database',
    }


def build_buckets(filters: BucketFilters) -> dict[str, Any]:
    query = _filtered_buckets(filters)
    total, bucket_count, container_count, systems_count, providers_count, latest = (
        query.order_by(None).with_entities(
            func.count(ObjectStorageBucket.id),
            func.sum(case((ObjectStorageBucket.native_type == 'bucket', 1), else_=0)),
            func.sum(case((ObjectStorageBucket.native_type == 'container', 1), else_=0)),
            func.count(func.distinct(ObjectStorageBucket.object_storage_system_id)),
            func.count(func.distinct(IntegrationInstance.provider_key)),
            func.max(ObjectStorageBucket.observed_at),
        ).one()
    )
    paged, pagination = paginate_query(
        query.options(joinedload(ObjectStorageBucket.object_storage_system)),
        page=filters.page,
        per_page=filters.per_page,
    )
    owner_cache: dict[str, ManagedAssetOwner | None] = {}
    rows = [_bucket_row(bucket, owner_cache=owner_cache) for bucket in paged]
    types = {
        value for (value,) in ObjectStorageBucket.query.with_entities(
            ObjectStorageBucket.native_type
        ).distinct().all() if value
    }
    systems = ObjectStorageSystem.query.with_entities(
        ObjectStorageSystem.id, ObjectStorageSystem.name
    ).order_by(ObjectStorageSystem.name.asc(), ObjectStorageSystem.id.asc()).all()
    total_committed_assets = ObjectStorageBucket.query.count()
    snapshot = _committed_system_snapshot()
    return {
        'assets': rows,
        'buckets': rows,
        'pagination': pagination,
        'total_assets': int(total or 0),
        'total_committed_assets': total_committed_assets,
        'total_buckets': int(bucket_count or 0),
        'total_containers': int(container_count or 0),
        'systems_in_scope': int(systems_count or 0),
        'providers_in_scope': int(providers_count or 0),
        'types': [
            {'value': value, 'label': _native_type_label(value)}
            for value in sorted(types)
        ],
        'latest_observed_at': latest,
        'setup': _setup_state(ObjectStorageSystem.query.count()),
        'snapshot': snapshot,
        'empty_state': _bucket_empty_state(total_committed_assets, snapshot),
        'systems': [{'id': system_id, 'name': name} for system_id, name in systems],
        **_system_options(),
    }


def build_bucket_detail(bucket_id: int) -> dict[str, Any] | None:
    bucket = (
        ObjectStorageBucket.query.options(joinedload(ObjectStorageBucket.object_storage_system))
        .filter(ObjectStorageBucket.id == bucket_id)
        .first()
    )
    return _bucket_row(bucket) if bucket is not None else None
