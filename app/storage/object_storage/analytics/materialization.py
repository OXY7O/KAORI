from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.common.analytics.metrics import MetricReadinessState, MetricsSourceError
from app.extensions.db import db
from app.models.object_storage import ObjectStorageSystem
from app.models.object_storage_analytics import ObjectStorageForecastSnapshot
from app.storage.object_storage.analytics.forecasting import linear_forecast
from app.storage.object_storage.analytics.sources import resolve_object_storage_metrics_source

FORECAST_METHOD = 'linear-v1'


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def required_contract_ready(source) -> bool:
    required = [item for item in source.readiness.items if item.tier == 'required']
    return bool(required) and all(item.state == MetricReadinessState.READY for item in required)


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
        snapshot = ObjectStorageForecastSnapshot(
            object_storage_system_id=str(system_id),
            history_window=history_window,
            method=FORECAST_METHOD,
        )
        db.session.add(snapshot)
    snapshot.status = 'pending'
    snapshot.last_attempt_at = datetime.now(UTC)
    snapshot.last_error = None
    snapshot.freshness_minutes = max(int(freshness_minutes), 5)
    snapshot.stale_grace_minutes = max(int(stale_grace_minutes), 15)
    snapshot.last_job_execution_id = job_execution_id
    db.session.commit()
    return snapshot


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
            raise RuntimeError('Object Storage consumer metrics contract is not Ready for forecasting.')
        capacity = source.scalar('object_storage.capacity.total_bytes')
        points = source.trend('object_storage.usage.total_bytes', history_window)
        if len(points) < 2:
            raise RuntimeError(
                f'Object Storage forecast history {history_window} returned fewer than two usable samples.'
            )
        forecast = linear_forecast(points, capacity_bytes=capacity)
        now = datetime.now(UTC)
        snapshot.payload_json = {
            'method': FORECAST_METHOD,
            'history_window': history_window,
            'capacity_bytes': capacity,
            'points': points,
            'forecast': forecast,
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
