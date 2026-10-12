"""Provider-neutral, bounded Registry historical Metrics Source materialization.

The external Metrics Source remains authoritative. No history is invented from
the creation age of current snapshots or from a prior committed counter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil, isfinite
from typing import Any

from app.integrations.observability.metrics_source.application.consumer import MetricsConsumer
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles.registry_harbor_v1 import (
    get_registry_query_expression,
)
from app.models.integration import IntegrationInstance

REGISTRY_HISTORY_WINDOWS: dict[str, timedelta] = {
    '1h': timedelta(hours=1),
    '6h': timedelta(hours=6),
    '12h': timedelta(hours=12),
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '60d': timedelta(days=60),
}
MAX_HISTORY_POINTS = 240
MAX_HISTORY_SERIES = 250
HISTORY_QUERIES = {
    'project_usage_bytes': 'registry.project.quota.usage_bytes',
    'project_quota_bytes': 'registry.project.quota.bytes',
    'project_artifacts': 'registry.project.artifacts',
    'project_pull_count': 'registry.project.pull_count',
    'request_rate_per_second': 'registry.core.request_rate',
}


def history_plan(window: str, *, now: datetime | None = None) -> tuple[datetime, datetime, int]:
    if window not in REGISTRY_HISTORY_WINDOWS:
        raise ValueError(f'Unsupported measured Registry history interval: {window}')
    end = now or datetime.now(UTC)
    start = end - REGISTRY_HISTORY_WINDOWS[window]
    step_seconds = max(60, ceil(REGISTRY_HISTORY_WINDOWS[window].total_seconds() / (MAX_HISTORY_POINTS - 1)))
    return start, end, step_seconds


def _bounded_matrix(result: Any, *, project_scoped: bool) -> dict[str, dict[str, float]]:
    if not isinstance(result, dict) or result.get('status') != 'success':
        raise ValueError('Metrics Source range query did not report success.')
    data = result.get('data')
    if not isinstance(data, dict) or data.get('resultType') != 'matrix':
        raise ValueError('Metrics Source range query did not return a matrix.')
    rows = data.get('result')
    if not isinstance(rows, list) or not rows:
        raise ValueError('No usable historical series were observed in the requested interval.')
    if len(rows) > MAX_HISTORY_SERIES:
        raise ValueError('Historical series count exceeds the Registry source budget.')

    normalized: dict[str, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('A historical series record is malformed.')
        labels = row.get('metric')
        if not isinstance(labels, dict):
            raise ValueError('Historical series labels are malformed.')
        project = str(labels.get('project_name') or '').strip() if project_scoped else '_aggregate'
        if not project or project in normalized:
            raise ValueError('Historical source labels are missing or ambiguous.')
        samples = row.get('values')
        if not isinstance(samples, list) or not samples or len(samples) > MAX_HISTORY_POINTS:
            raise ValueError('Historical range series is empty or exceeds the sample budget.')
        points: list[tuple[float, float]] = []
        for sample in samples:
            if not isinstance(sample, (list, tuple)) or len(sample) != 2:
                raise ValueError('Historical series sample is malformed.')
            try:
                timestamp, value = float(sample[0]), float(sample[1])
            except (TypeError, ValueError) as exc:
                raise ValueError('Historical sample is nonnumeric.') from exc
            if not isfinite(timestamp) or not isfinite(value):
                raise ValueError('Historical sample is not finite.')
            points.append((timestamp, value))
        if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
            raise ValueError('Historical sample timestamps are not strictly increasing.')
        normalized[project] = {
            'start_time': points[0][0],
            'end_time': points[-1][0],
            'first': points[0][1],
            'last': points[-1][1],
            'samples': len(points),
        }
    return normalized


def collect_registry_metric_history(
    identity: IntegrationInstance,
    window: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    start, end, step = history_plan(window, now=now)
    history: dict[str, Any] = {
        'time_range': window,
        'start_at': start.isoformat(),
        'end_at': end.isoformat(),
        'step_seconds': step,
        'max_series': MAX_HISTORY_SERIES,
        'max_samples_per_series': MAX_HISTORY_POINTS,
        'source': 'metrics_source_query_range',
        'series': {},
    }
    errors: dict[str, str] = {}
    values: dict[str, dict[str, dict[str, float]]] = {}

    try:
        consumer = MetricsConsumer.for_asset(
            scope_type='registry_instance',
            scope_key=identity.id,
            scope_name=identity.name,
        )
    except MetricsSourceError as exc:
        errors['binding'] = str(exc)
        history.update({'status': 'unavailable', 'capability_gaps': errors})
        return history, {'status': 'unavailable', 'capability_gaps': errors}, {}

    for field, key in HISTORY_QUERIES.items():
        try:
            result = consumer.query_range(
                get_registry_query_expression(key),
                start.isoformat(),
                end.isoformat(),
                f'{step}s',
                retry_count=0,
            )
            values[field] = _bounded_matrix(result, project_scoped=field != 'request_rate_per_second')
        except (MetricsSourceError, ValueError) as exc:
            errors[key] = str(exc)[:500]

    successful = len(values)
    status = 'unavailable' if not successful else ('partial' if errors else 'ready')
    history.update({
        'status': status,
        'metrics_source': consumer.config.name,
        'binding_id': consumer.binding.id,
        'capability_gaps': errors,
        'series': values,
    })
    current_metrics: dict[str, Any] = {
        'status': status,
        'metrics_source': consumer.config.name,
        'binding_id': consumer.binding.id,
        'capability_gaps': errors,
    }
    for field in ('project_usage_bytes', 'project_quota_bytes', 'project_artifacts', 'project_pull_count'):
        current_metrics[field] = {
            project: point['last'] for project, point in values.get(field, {}).items()
        }
    rate = values.get('request_rate_per_second', {}).get('_aggregate')
    current_metrics['request_rate_per_second'] = rate['last'] if rate else None

    elapsed_days = (end - start).total_seconds() / 86400
    artifacts = values.get('project_artifacts', {})
    sizes = values.get('project_usage_bytes', {})
    artifact_delta = sum(point['last'] - point['first'] for point in artifacts.values()) if artifacts else None
    size_delta = sum(point['last'] - point['first'] for point in sizes.values()) if sizes else None
    growth = {
        'elapsed_days': elapsed_days,
        'artifact_delta': artifact_delta,
        'size_delta_bytes': size_delta,
        'artifact_growth_per_day': artifact_delta / elapsed_days if artifact_delta is not None else None,
        'size_growth_bytes_per_day': size_delta / elapsed_days if size_delta is not None else None,
        'source': 'metrics_source_range' if artifact_delta is not None or size_delta is not None else 'unavailable',
    }
    return history, current_metrics, growth
