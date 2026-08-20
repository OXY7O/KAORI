from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.analytics.metrics import MetricReadinessState, MetricsSourceError
from app.extensions.db import db
from app.models.object_storage import ObjectStorageSystem
from app.models.object_storage_analytics import ObjectStorageAnalyticsSnapshot, ObjectStorageForecastSnapshot
from app.storage.object_storage.analytics.forecasting import linear_forecast
from app.storage.object_storage.analytics.sources import resolve_object_storage_metrics_source

ANALYTICS_SNAPSHOT_SCHEMA = 'object-storage-analytics.v1'
FORECAST_METHOD = 'linear-v1'


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _encode_snapshot_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return {'__kaori_object_storage_type__': 'datetime', 'value': value.isoformat()}
    if isinstance(value, dict):
        return {str(key): _encode_snapshot_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_encode_snapshot_value(item) for item in value]
    raise TypeError(f'Unsupported Object Storage analytics snapshot value: {type(value).__name__}')


def _decode_snapshot_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_snapshot_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get('__kaori_object_storage_type__') == 'datetime':
        return datetime.fromisoformat(str(value['value']))
    return {key: _decode_snapshot_value(item) for key, item in value.items()}


def get_analytics_snapshot(*, system_id: str, time_range: str) -> ObjectStorageAnalyticsSnapshot | None:
    return ObjectStorageAnalyticsSnapshot.query.filter_by(
        object_storage_system_id=str(system_id),
        time_range=time_range,
    ).first()


def analytics_snapshot_state(snapshot: ObjectStorageAnalyticsSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {
            'state': 'missing',
            'label': 'Worker Data Required',
            'tone': 'warning',
            'usable': False,
            'stale': False,
            'generated_at': None,
            'last_attempt_at': None,
            'last_error': None,
        }
    now = datetime.now(UTC)
    generated_at = _aware(snapshot.generated_at)
    expires_at = _aware(snapshot.expires_at)
    stale_deadline = (
        expires_at + timedelta(minutes=max(int(snapshot.stale_grace_minutes or 0), 0))
        if expires_at is not None
        else None
    )
    has_payload = isinstance(snapshot.payload_json, dict) and generated_at is not None
    if snapshot.status == 'pending':
        label, tone = ('Refreshing · Last Snapshot Available', 'info') if has_payload else ('Refreshing', 'pending')
    elif snapshot.status == 'failed':
        label, tone = ('Stale · Last Refresh Failed', 'warning') if has_payload else ('Worker Failed', 'critical')
    elif not has_payload:
        label, tone = 'Worker Data Required', 'warning'
    elif expires_at is not None and now <= expires_at:
        label, tone = 'Current', 'normal'
    elif stale_deadline is not None and now <= stale_deadline:
        label, tone = 'Stale', 'warning'
    else:
        label, tone = 'Expired', 'critical'
    usable = bool(has_payload and stale_deadline is not None and now <= stale_deadline)
    stale = bool(usable and expires_at is not None and now > expires_at)
    return {
        'state': snapshot.status,
        'label': label,
        'tone': tone,
        'usable': usable,
        'stale': stale,
        'generated_at': snapshot.generated_at,
        'last_attempt_at': snapshot.last_attempt_at,
        'last_error': snapshot.last_error,
    }


def read_analytics_snapshot(*, system_id: str, time_range: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    snapshot = get_analytics_snapshot(system_id=system_id, time_range=time_range)
    state = analytics_snapshot_state(snapshot)
    state['time_range'] = time_range
    if snapshot is None or not state['usable'] or not isinstance(snapshot.payload_json, dict):
        return None, state
    payload = _decode_snapshot_value(snapshot.payload_json)
    if not isinstance(payload, dict) or payload.get('schema') != ANALYTICS_SNAPSHOT_SCHEMA:
        return None, {**state, 'usable': False, 'label': 'Snapshot Contract Invalid', 'tone': 'critical'}
    return payload, state


def mark_analytics_pending(
    *,
    system_id: str,
    time_range: str,
    freshness_minutes: int,
    stale_grace_minutes: int,
    job_execution_id: int | None,
) -> ObjectStorageAnalyticsSnapshot:
    snapshot = get_analytics_snapshot(system_id=system_id, time_range=time_range)
    if snapshot is None:
        snapshot = ObjectStorageAnalyticsSnapshot()
        snapshot.object_storage_system_id = str(system_id)
        snapshot.time_range = time_range
        db.session.add(snapshot)
    snapshot.status = 'pending'
    snapshot.last_attempt_at = datetime.now(UTC)
    snapshot.last_error = None
    snapshot.freshness_minutes = max(int(freshness_minutes), 5)
    snapshot.stale_grace_minutes = max(int(stale_grace_minutes), 15)
    snapshot.last_job_execution_id = job_execution_id
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        snapshot = ObjectStorageAnalyticsSnapshot.query.filter_by(
            object_storage_system_id=str(system_id),
            time_range=time_range,
        ).one()
    return snapshot


def store_analytics_snapshot(
    *,
    system_id: str,
    time_range: str,
    payload: dict[str, Any],
    freshness_minutes: int,
    stale_grace_minutes: int,
    job_execution_id: int | None,
) -> ObjectStorageAnalyticsSnapshot:
    snapshot = mark_analytics_pending(
        system_id=system_id,
        time_range=time_range,
        freshness_minutes=freshness_minutes,
        stale_grace_minutes=stale_grace_minutes,
        job_execution_id=job_execution_id,
    )
    now = datetime.now(UTC)
    snapshot.payload_json = _encode_snapshot_value({'schema': ANALYTICS_SNAPSHOT_SCHEMA, **payload})
    snapshot.status = 'ready'
    snapshot.generated_at = now
    snapshot.expires_at = now + timedelta(minutes=max(int(freshness_minutes), 5))
    snapshot.last_attempt_at = now
    snapshot.last_error = None
    snapshot.last_job_execution_id = job_execution_id
    db.session.commit()
    return snapshot


def fail_analytics_snapshot(
    *,
    system_id: str,
    time_range: str,
    error: Exception | str,
    freshness_minutes: int,
    stale_grace_minutes: int,
    job_execution_id: int | None,
) -> None:
    snapshot = mark_analytics_pending(
        system_id=system_id,
        time_range=time_range,
        freshness_minutes=freshness_minutes,
        stale_grace_minutes=stale_grace_minutes,
        job_execution_id=job_execution_id,
    )
    snapshot.status = 'failed'
    snapshot.last_attempt_at = datetime.now(UTC)
    snapshot.last_error = str(error)[:4000]
    snapshot.last_job_execution_id = job_execution_id
    db.session.commit()


def analytics_snapshot_due(*, system_id: str, time_range: str) -> bool:
    snapshot = get_analytics_snapshot(system_id=system_id, time_range=time_range)
    if snapshot is None or snapshot.payload_json is None or snapshot.generated_at is None:
        return True
    expires_at = _aware(snapshot.expires_at)
    return expires_at is None or datetime.now(UTC) >= expires_at


_READINESS_STATE_LABELS = {
    MetricReadinessState.READY: 'Ready',
    MetricReadinessState.PARTIAL: 'Partial Evidence',
    MetricReadinessState.NO_DATA: 'No Current Samples',
    MetricReadinessState.UNSUPPORTED: 'Metric Not Scraped',
    MetricReadinessState.BLOCKED: 'Metric Contract Blocked',
    MetricReadinessState.NOT_VALIDATED: 'Validation Required',
}


def required_contract_status(source) -> dict[str, Any]:
    required = [item for item in source.readiness.items if item.tier == 'required']
    missing = [item for item in required if item.state != MetricReadinessState.READY]
    return {
        'ready': bool(required) and not missing,
        'ready_count': len(required) - len(missing),
        'total_count': len(required),
        'missing': [
            {
                'key': item.key,
                'label': item.label,
                'domain': item.domain,
                'state': item.state.value,
                'state_label': _READINESS_STATE_LABELS.get(
                    item.state,
                    item.state.value.replace('_', ' ').title(),
                ),
                'detail': item.detail,
            }
            for item in missing
        ],
    }


def required_contract_ready(source) -> bool:
    return bool(required_contract_status(source)['ready'])


def required_contract_diagnostic(source, *, max_items: int = 4) -> str:
    status = required_contract_status(source)
    ready_count = int(status['ready_count'])
    total_count = int(status['total_count'])
    if status['ready']:
        return f'Required Metrics Contract Ready · {ready_count}/{total_count} Ready.'

    missing = list(status['missing'])
    headline = f'Required Metrics Contract Incomplete · {ready_count}/{total_count} Ready'
    if not missing:
        return f'{headline}. Run consumer binding validation to rebuild required metric evidence.'

    visible = missing[: max(int(max_items), 1)]
    missing_text = '; '.join(f'{item["label"]} — {item["state_label"]}' for item in visible)
    remaining = len(missing) - len(visible)
    suffix = f'; +{remaining} more' if remaining > 0 else ''
    detail = str(visible[0].get('detail') or '').strip() if len(missing) == 1 else ''
    action = f' {detail}' if detail else ''
    return f'{headline}. Missing: {missing_text}{suffix}.{action}'.strip()


def get_forecast_snapshot(
    *,
    system_id: str,
    history_window: str,
) -> ObjectStorageForecastSnapshot | None:
    return ObjectStorageForecastSnapshot.query.filter_by(
        object_storage_system_id=str(system_id),
        history_window=history_window,
        method=FORECAST_METHOD,
    ).first()


def forecast_snapshot_state(snapshot: ObjectStorageForecastSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {
            'state': 'missing',
            'label': 'Worker Data Required',
            'tone': 'warning',
            'usable': False,
            'generated_at': None,
            'last_attempt_at': None,
            'last_error': None,
        }
    now = datetime.now(UTC)
    generated_at = _aware(snapshot.generated_at)
    expires_at = _aware(snapshot.expires_at)
    stale_deadline = (
        expires_at + timedelta(minutes=max(int(snapshot.stale_grace_minutes or 0), 0))
        if expires_at is not None
        else None
    )
    has_payload = isinstance(snapshot.payload_json, dict) and generated_at is not None
    if snapshot.status == 'pending':
        label, tone = 'Refreshing', 'pending'
    elif snapshot.status == 'failed':
        label, tone = ('Stale · Last Refresh Failed', 'warning') if has_payload else ('Worker Failed', 'critical')
    elif not has_payload:
        label, tone = 'Worker Data Required', 'warning'
    elif expires_at is not None and now <= expires_at:
        label, tone = 'Current', 'normal'
    elif stale_deadline is not None and now <= stale_deadline:
        label, tone = 'Stale', 'warning'
    else:
        label, tone = 'Expired', 'critical'
    usable = bool(has_payload and stale_deadline is not None and now <= stale_deadline)
    return {
        'state': snapshot.status,
        'label': label,
        'tone': tone,
        'usable': usable,
        'generated_at': snapshot.generated_at,
        'last_attempt_at': snapshot.last_attempt_at,
        'last_error': snapshot.last_error,
    }


def mark_forecast_pending(
    *,
    system_id: str,
    history_window: str,
    freshness_minutes: int,
    stale_grace_minutes: int,
    job_execution_id: int | None,
) -> ObjectStorageForecastSnapshot:
    snapshot = get_forecast_snapshot(system_id=system_id, history_window=history_window)
    if snapshot is None:
        snapshot = ObjectStorageForecastSnapshot()
        snapshot.object_storage_system_id = str(system_id)
        snapshot.history_window = history_window
        snapshot.method = FORECAST_METHOD
        db.session.add(snapshot)
    snapshot.status = 'pending'
    snapshot.last_attempt_at = datetime.now(UTC)
    snapshot.last_error = None
    snapshot.freshness_minutes = max(int(freshness_minutes), 5)
    snapshot.stale_grace_minutes = max(int(stale_grace_minutes), 15)
    snapshot.last_job_execution_id = job_execution_id
    db.session.commit()
    return snapshot


def _bucket_forecast_payload(
    *,
    system: ObjectStorageSystem,
    source,
    history_window: str,
) -> list[dict[str, Any]]:
    series = source.trend_vector('object_storage.bucket.usage_history', history_window, 'bucket')
    inventory = {bucket.name: bucket for bucket in system.buckets or ()}
    names = sorted(set(inventory) | set(series))
    rows: list[dict[str, Any]] = []
    for name in names:
        points = series.get(name) or []
        bucket = inventory.get(name)
        quota_bytes = float(bucket.quota_bytes) if bucket is not None and bucket.quota_bytes is not None else None
        if len(points) >= 2:
            forecast = linear_forecast(points, capacity_bytes=quota_bytes)
            history_state = 'ready'
        else:
            forecast = {
                'growth_per_day': None,
                'projected_7d': None,
                'projected_30d': None,
                'days_to_capacity': None,
            }
            history_state = 'partial' if points else 'no_data'
        current_bytes = float(points[-1]['value']) if points else None
        rows.append(
            {
                'name': name,
                'sample_count': len(points),
                'history_state': history_state,
                'current_bytes': current_bytes,
                'inventory_usage_bytes': float(bucket.size_bytes)
                if bucket is not None and bucket.size_bytes is not None
                else None,
                'quota_bytes': quota_bytes,
                'forecast': forecast,
            }
        )
    rows.sort(
        key=lambda row: (
            row.get('history_state') == 'ready',
            float(row.get('current_bytes') or row.get('inventory_usage_bytes') or 0),
        ),
        reverse=True,
    )
    return rows


def materialize_forecast(
    *,
    system: ObjectStorageSystem,
    history_window: str,
    freshness_minutes: int,
    stale_grace_minutes: int,
    job_execution_id: int | None,
) -> ObjectStorageForecastSnapshot:
    snapshot = mark_forecast_pending(
        system_id=system.id,
        history_window=history_window,
        freshness_minutes=freshness_minutes,
        stale_grace_minutes=stale_grace_minutes,
        job_execution_id=job_execution_id,
    )
    try:
        source = resolve_object_storage_metrics_source(system, execution_mode='background')
        if not required_contract_ready(source):
            raise RuntimeError(required_contract_diagnostic(source))
        capacity = source.scalar('object_storage.capacity.total_bytes')
        points = source.trend('object_storage.usage.total_bytes', history_window)
        if len(points) < 2:
            raise RuntimeError(
                f'Object Storage forecast history {history_window} returned fewer than two usable samples.'
            )
        forecast = linear_forecast(points, capacity_bytes=capacity)
        bucket_forecasts = _bucket_forecast_payload(
            system=system,
            source=source,
            history_window=history_window,
        )
        now = datetime.now(UTC)
        snapshot.payload_json = {
            'method': FORECAST_METHOD,
            'history_window': history_window,
            'capacity_bytes': capacity,
            'points': points,
            'forecast': forecast,
            'bucket_forecasts': bucket_forecasts,
            'source': {
                'provider_key': source.identity.provider_key,
                'provider_label': source.identity.provider_label,
                'instance_name': source.identity.instance_name,
            },
            'sample_count': len(points),
        }
        snapshot.status = 'ready'
        snapshot.generated_at = now
        snapshot.expires_at = now + timedelta(minutes=max(int(freshness_minutes), 5))
        snapshot.last_attempt_at = now
        snapshot.last_error = None
        snapshot.last_job_execution_id = job_execution_id
        db.session.commit()
        return snapshot
    except (MetricsSourceError, RuntimeError, SQLAlchemyError) as exc:
        db.session.rollback()
        snapshot = get_forecast_snapshot(system_id=system.id, history_window=history_window) or snapshot
        snapshot.status = 'failed'
        snapshot.last_attempt_at = datetime.now(UTC)
        snapshot.last_error = str(exc)[:2000]
        snapshot.last_job_execution_id = job_execution_id
        db.session.commit()
        raise


def forecast_snapshot_due(
    *,
    system_id: str,
    history_window: str,
) -> bool:
    snapshot = get_forecast_snapshot(system_id=system_id, history_window=history_window)
    if snapshot is None or snapshot.payload_json is None or snapshot.generated_at is None:
        return True
    expires_at = _aware(snapshot.expires_at)
    return expires_at is None or datetime.now(UTC) >= expires_at
