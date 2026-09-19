from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.analytics.materialization.service import read_last_known_snapshot
from app.storage.object_storage.analytics.alert_sources import resolve_materialized_alert_stream
from app.storage.object_storage.analytics.materialization import read_latest_known_analytics_snapshot

_SNAPSHOT_LABELS = {
    'fresh': ('Current Worker Snapshot', 'normal'),
    'stale': ('Stale · Last Good Snapshot', 'warning'),
    'expired': ('Last Good Snapshot', 'warning'),
    'failed': ('Refresh Failed · Last Good Snapshot', 'warning'),
    'refreshing': ('Refreshing · Last Good Snapshot', 'info'),
    'pending': ('Refreshing', 'pending'),
    'ready': ('Current Worker Snapshot', 'normal'),
    'missing': ('Worker Data Required', 'warning'),
    'invalid': ('Snapshot Contract Invalid', 'critical'),
    'blocked': ('Snapshot Unavailable', 'critical'),
}


def load_snapshot_rows(
    *,
    domain: str,
    asset_key: str,
    source: str,
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any], dict[str, Any]]:
    """Load Alert Intelligence evidence from committed worker snapshots only."""

    if not asset_key:
        return [], _empty_source_status(source), _missing_snapshot('No asset is selected.')
    if domain == 'kubernetes':
        return _load_kubernetes_snapshot(asset_key=asset_key, source=source)
    if domain == 'object_storage':
        return _load_object_storage_snapshot(asset_key=asset_key, source=source)
    return [], _empty_source_status(source), _missing_snapshot('The selected Intelligence domain is unsupported.')


def _load_kubernetes_snapshot(
    *,
    asset_key: str,
    source: str,
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any], dict[str, Any]]:
    result = read_last_known_snapshot(
        cluster_id=asset_key,
        dataset_key='analytics.alerts',
        parameters={'cluster_id': asset_key, 'source': source},
    )
    selection_fallback = False
    if not result.available and source != 'auto':
        fallback = read_last_known_snapshot(
            cluster_id=asset_key,
            dataset_key='analytics.alerts',
            parameters={'cluster_id': asset_key, 'source': 'auto'},
        )
        if fallback.available:
            result = fallback
            selection_fallback = True

    context = result.context or {}
    snapshot = _kubernetes_snapshot_meta(result, selection_fallback=selection_fallback)
    if not result.available:
        return [], _empty_source_status(source), snapshot

    raw_rows = [row for row in context.get('all_alerts') or [] if isinstance(row, Mapping)]
    raw_status = context.get('source_status')
    status = dict(raw_status) if isinstance(raw_status, Mapping) else _empty_source_status(source)
    status['selected_source'] = source
    if selection_fallback:
        status['fallback_used'] = True
        status['fallback_reason'] = (
            'A source-specific committed snapshot is not available yet. '
            'KAORI is showing the latest Automatic worker snapshot without querying the provider from this page.'
        )
    return raw_rows, status, snapshot


def _load_object_storage_snapshot(
    *,
    asset_key: str,
    source: str,
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any], dict[str, Any]]:
    payload, state = read_latest_known_analytics_snapshot(system_id=asset_key)
    snapshot = _object_storage_snapshot_meta(state)
    if payload is None:
        return [], _empty_source_status(source), snapshot

    streams_value = payload.get('alert_streams')
    streams = dict(streams_value) if isinstance(streams_value, Mapping) else {}
    stream = resolve_materialized_alert_stream(streams, selected_source=source)
    raw_rows = [row for row in stream.get('rows') or [] if isinstance(row, Mapping)]
    return raw_rows, stream, snapshot


def _kubernetes_snapshot_meta(result, *, selection_fallback: bool) -> dict[str, Any]:
    snapshot = result.snapshot
    label, tone = _SNAPSHOT_LABELS.get(result.state, ('Last Good Snapshot', 'warning'))
    available = bool(result.available)
    serving_last_good = bool(available and (result.stale or result.state in {'failed', 'refreshing', 'expired'}))
    return {
        'available': available,
        'state': result.state,
        'label': label,
        'tone': tone,
        'stale': bool(result.stale),
        'serving_last_good': serving_last_good,
        'selection_fallback': selection_fallback,
        'generated_at': snapshot.generated_at if snapshot is not None else None,
        'last_attempt_at': snapshot.last_attempt_at if snapshot is not None else None,
        'last_error': snapshot.last_error if snapshot is not None else None,
        'refresh_owner': 'Kubernetes Analytics Data Refresh',
    }


def _object_storage_snapshot_meta(state: Mapping[str, Any]) -> dict[str, Any]:
    available = bool(state.get('last_known_available'))
    raw_state = str(state.get('state') or 'missing')
    usable = bool(state.get('usable'))
    stale = bool(state.get('stale'))
    if available and raw_state == 'failed':
        label, tone = _SNAPSHOT_LABELS['failed']
    elif available and raw_state == 'pending':
        label, tone = _SNAPSHOT_LABELS['refreshing']
    elif available and usable and stale:
        label, tone = _SNAPSHOT_LABELS['stale']
    elif available and usable:
        label, tone = _SNAPSHOT_LABELS['fresh']
    elif available:
        label, tone = _SNAPSHOT_LABELS['expired']
    else:
        label, tone = _SNAPSHOT_LABELS.get(raw_state, _SNAPSHOT_LABELS['missing'])
    return {
        'available': available,
        'state': raw_state,
        'label': label,
        'tone': tone,
        'stale': bool(stale or (available and not usable)),
        'serving_last_good': bool(available and (raw_state != 'ready' or not usable or stale)),
        'selection_fallback': False,
        'generated_at': state.get('generated_at'),
        'last_attempt_at': state.get('last_attempt_at'),
        'last_error': state.get('last_error'),
        'refresh_owner': 'Object Storage Analytics Data Refresh',
    }


def _empty_source_status(source: str) -> dict[str, Any]:
    return {
        'selected_source': source,
        'resolved_source': 'none',
        'resolved_label': 'None',
        'label': 'Worker Snapshot Required',
        'configured': False,
        'connected': False,
        'fallback_used': False,
        'fallback_reason': None,
        'error': None,
        'instance_name': None,
    }


def _missing_snapshot(detail: str) -> dict[str, Any]:
    return {
        'available': False,
        'state': 'missing',
        'label': 'Worker Data Required',
        'tone': 'warning',
        'stale': False,
        'serving_last_good': False,
        'selection_fallback': False,
        'generated_at': None,
        'last_attempt_at': None,
        'last_error': None,
        'refresh_owner': None,
        'detail': detail,
    }
