from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

OVERVIEW_SNAPSHOT_DATASETS: dict[str, str] = {
    'analytics.utilization.summary': 'Utilization Summary',
    'analytics.capacity': 'Capacity Analysis',
    'analytics.storage': 'Storage Analysis',
    'analytics.workload': 'Workload Analysis',
    'analytics.top_consumers': 'Top Consumers',
    'analytics.forecast': 'Resource Forecast',
    'analytics.alerts': 'Alerts and Anomalies',
}

ANALYTICS_TIME_RANGE_LABELS: dict[str, str] = {
    '1h': 'Last 1 Hour',
    '6h': 'Last 6 Hours',
    '12h': 'Last 12 Hours',
    '24h': 'Last 24 Hours',
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '60d': 'Last 60 Days',
}


def overview_snapshot_parameters(*, cluster_id: str, time_range: str) -> dict[str, dict[str, str]]:
    forecast_history_window = time_range if time_range in {'7d', '30d'} else '30d'
    cluster_scope = {'cluster_id': str(cluster_id)} if cluster_id else {}
    return {
        'analytics.utilization.summary': dict(cluster_scope),
        'analytics.capacity': {**cluster_scope, 'time_range': time_range},
        'analytics.storage': dict(cluster_scope),
        'analytics.workload': {**cluster_scope, 'time_range': time_range},
        'analytics.top_consumers': dict(cluster_scope),
        'analytics.forecast': {**cluster_scope, 'history_window': forecast_history_window},
        'analytics.alerts': {**cluster_scope, 'source': 'auto'},
    }


def present_snapshot_summary(
    snapshots: list[Any],
    *,
    time_range: str,
    now: datetime | None = None,
    expected_parameters: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    current_time = _normalize_datetime(now or datetime.now(UTC))
    latest_by_dataset = _latest_matching_snapshots(
        snapshots,
        expected_parameters=expected_parameters,
    )
    dataset_states = _build_dataset_states(latest_by_dataset, current_time=current_time)
    counts = _count_dataset_states(dataset_states)
    latest_snapshot = _latest_snapshot(latest_by_dataset, 'generated_at')
    latest_attempt = _latest_snapshot(latest_by_dataset, 'last_attempt_at')
    status = _summary_status(counts)
    latest_dataset_key = str(getattr(latest_snapshot, 'dataset_key', '') or '')

    return {
        **status,
        'latest_generated_at': _format_snapshot_datetime(
            getattr(latest_snapshot, 'generated_at', None) if latest_snapshot else None
        ),
        'latest_attempt_at': _format_snapshot_datetime(
            getattr(latest_attempt, 'last_attempt_at', None) if latest_attempt else None
        ),
        'latest_dataset': OVERVIEW_SNAPSHOT_DATASETS.get(latest_dataset_key, 'No Snapshot'),
        **counts,
        'missing_dataset_count': max(len(OVERVIEW_SNAPSHOT_DATASETS) - len(latest_by_dataset), 0),
        'analysis_window': ANALYTICS_TIME_RANGE_LABELS.get(time_range, time_range or 'Default'),
        'datasets': dataset_states,
    }


def _latest_matching_snapshots(
    snapshots: list[Any],
    *,
    expected_parameters: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    latest_by_dataset: dict[str, Any] = {}
    for snapshot in snapshots:
        dataset_key = str(getattr(snapshot, 'dataset_key', '') or '')
        if dataset_key not in OVERVIEW_SNAPSHOT_DATASETS:
            continue
        if not _matches_parameters(snapshot, dataset_key, expected_parameters):
            continue
        previous = latest_by_dataset.get(dataset_key)
        if previous is None or _snapshot_sort_value(snapshot) > _snapshot_sort_value(previous):
            latest_by_dataset[dataset_key] = snapshot
    return latest_by_dataset


def _matches_parameters(
    snapshot: Any,
    dataset_key: str,
    expected_parameters: dict[str, dict[str, str]] | None,
) -> bool:
    if expected_parameters is None:
        return True
    expected = expected_parameters.get(dataset_key, {})
    actual = _normalize_snapshot_parameters(getattr(snapshot, 'parameters_json', {}))
    return actual == expected


def _build_dataset_states(
    latest_by_dataset: dict[str, Any],
    *,
    current_time: datetime,
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for dataset_key, label in OVERVIEW_SNAPSHOT_DATASETS.items():
        snapshot = latest_by_dataset.get(dataset_key)
        states[dataset_key] = _dataset_state(snapshot, label=label, current_time=current_time)
    return states


def _dataset_state(snapshot: Any | None, *, label: str, current_time: datetime) -> dict[str, Any]:
    if snapshot is None:
        return {'label': label, 'state': 'missing', 'available': False, 'current': False}

    status = str(getattr(snapshot, 'status', '') or '').lower()
    expires_at = _normalize_datetime(getattr(snapshot, 'expires_at', None))
    is_stale = status == 'ready' and expires_at is not None and expires_at <= current_time
    state = 'stale' if is_stale else ('current' if status == 'ready' else status or 'unknown')
    return {
        'label': label,
        'state': state,
        'available': status == 'ready',
        'current': status == 'ready' and not is_stale,
    }


def _count_dataset_states(states: dict[str, dict[str, Any]]) -> dict[str, int]:
    values = list(states.values())
    return {
        'current_dataset_count': sum(1 for item in values if item['state'] == 'current'),
        'available_dataset_count': sum(1 for item in values if item['available']),
        'expected_dataset_count': len(OVERVIEW_SNAPSHOT_DATASETS),
        'stale_dataset_count': sum(1 for item in values if item['state'] == 'stale'),
        'pending_dataset_count': sum(1 for item in values if item['state'] == 'pending'),
        'failed_dataset_count': sum(1 for item in values if item['state'] == 'failed'),
    }


def _summary_status(counts: dict[str, int]) -> dict[str, str]:
    expected = counts['expected_dataset_count']
    if counts['pending_dataset_count']:
        return {
            'status': 'Refresh In Progress',
            'tone': 'info',
            'description': 'One or more analytics datasets are currently being materialized by the worker.',
        }
    if counts['current_dataset_count'] == expected:
        return {
            'status': 'Current',
            'tone': 'normal',
            'description': 'All Analytics Overview datasets are available within their configured freshness windows.',
        }
    if counts['current_dataset_count'] > 0:
        return {
            'status': 'Partially Current',
            'tone': 'warning',
            'description': 'Current snapshot data is available, but one or more analytics domains still need refresh.',
        }
    if counts['stale_dataset_count'] > 0:
        return {
            'status': 'Stale',
            'tone': 'warning',
            'description': 'Only expired snapshot data is currently available for this cluster.',
        }
    if counts['failed_dataset_count'] > 0:
        return {
            'status': 'Failed',
            'tone': 'critical',
            'description': 'The latest materialization attempt failed before producing current analytics data.',
        }
    return {
        'status': 'Unavailable',
        'tone': 'unknown',
        'description': 'No committed Analytics Overview snapshot is available for this cluster.',
    }


def _latest_snapshot(latest_by_dataset: dict[str, Any], attribute: str) -> Any | None:
    candidates = [item for item in latest_by_dataset.values() if getattr(item, attribute, None) is not None]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: _normalize_datetime(getattr(item, attribute, None))
        or datetime.min.replace(tzinfo=UTC),
    )


def _normalize_snapshot_parameters(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in sorted(value.items())
        if item is not None and str(item).strip() != ''
    }


def _snapshot_sort_value(snapshot: Any) -> datetime:
    for attribute in ('generated_at', 'updated_at', 'last_attempt_at', 'created_at'):
        value = _normalize_datetime(getattr(snapshot, attribute, None))
        if value is not None:
            return value
    return datetime.min.replace(tzinfo=UTC)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_snapshot_datetime(value: datetime | None) -> str:
    normalized = _normalize_datetime(value)
    if normalized is None:
        return 'Not Available'
    return normalized.strftime('%Y-%m-%d %H:%M UTC')
