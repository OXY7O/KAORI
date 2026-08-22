from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions.db import db
from app.kubernetes.analytics.materialization.catalog import canonical_parameters, get_dataset
from app.kubernetes.analytics.materialization.identity import parameter_fingerprint
from app.kubernetes.analytics.materialization.serialization import decode_value, encode_value
from app.models import AnalyticsSnapshot


def utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    context: dict[str, Any] | None
    snapshot: AnalyticsSnapshot | None
    state: str
    stale: bool

    @property
    def available(self) -> bool:
        return self.context is not None


def get_snapshot(
    *,
    cluster_id: str,
    dataset_key: str,
    parameters: dict[str, Any] | None,
) -> AnalyticsSnapshot | None:
    normalized = canonical_parameters(dataset_key, parameters)
    return AnalyticsSnapshot.query.filter_by(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameter_fingerprint=parameter_fingerprint(normalized),
    ).first()


def read_snapshot(
    *,
    cluster_id: str,
    dataset_key: str,
    parameters: dict[str, Any] | None,
) -> SnapshotResult:
    snapshot = get_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
    )
    if snapshot is None or snapshot.payload_json is None or snapshot.generated_at is None:
        return SnapshotResult(None, snapshot, snapshot.status if snapshot else 'missing', False)

    dataset = get_dataset(dataset_key)
    now = utcnow()
    generated_at = _as_utc(snapshot.generated_at)
    expires_at = (
        _as_utc(snapshot.expires_at)
        if snapshot.expires_at
        else generated_at + timedelta(minutes=dataset.freshness_minutes)
    )
    stale_deadline = expires_at + timedelta(minutes=snapshot.stale_grace_minutes or dataset.stale_grace_minutes)
    if now > stale_deadline:
        return SnapshotResult(None, snapshot, 'expired', True)

    context = decode_value(snapshot.payload_json)
    if not isinstance(context, dict):
        current_app.logger.error('Analytics snapshot %s did not decode to a context mapping.', snapshot.id)
        return SnapshotResult(None, snapshot, 'invalid', False)
    if context.get('dependency_blocker'):
        current_app.logger.warning(
            'Analytics snapshot %s contains a dependency blocker and will not be served as ready data.',
            snapshot.id,
        )
        return SnapshotResult(None, snapshot, 'blocked', False)
    return SnapshotResult(context, snapshot, 'stale' if now > expires_at else 'fresh', now > expires_at)


def read_last_known_snapshot(
    *,
    cluster_id: str,
    dataset_key: str,
    parameters: dict[str, Any] | None,
) -> SnapshotResult:
    """Read the last committed payload even after its normal stale-grace window.

    This reader is intended for read-only continuity surfaces such as Intelligence.
    It never performs provider I/O and never treats old evidence as current; callers
    must surface the returned state and timestamps alongside the preserved payload.
    """

    snapshot = get_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
    )
    if snapshot is None or snapshot.payload_json is None or snapshot.generated_at is None:
        return SnapshotResult(None, snapshot, snapshot.status if snapshot else 'missing', False)

    context = decode_value(snapshot.payload_json)
    if not isinstance(context, dict):
        current_app.logger.error('Analytics snapshot %s did not decode to a context mapping.', snapshot.id)
        return SnapshotResult(None, snapshot, 'invalid', False)
    if context.get('dependency_blocker'):
        current_app.logger.warning(
            'Analytics snapshot %s contains a dependency blocker and cannot be served as last-known evidence.',
            snapshot.id,
        )
        return SnapshotResult(None, snapshot, 'blocked', False)

    dataset = get_dataset(dataset_key)
    now = utcnow()
    generated_at = _as_utc(snapshot.generated_at)
    expires_at = (
        _as_utc(snapshot.expires_at)
        if snapshot.expires_at
        else generated_at + timedelta(minutes=dataset.freshness_minutes)
    )
    stale_deadline = expires_at + timedelta(minutes=snapshot.stale_grace_minutes or dataset.stale_grace_minutes)
    if snapshot.status == 'failed':
        state = 'failed'
    elif snapshot.status == 'pending':
        state = 'refreshing'
    elif now <= expires_at:
        state = 'fresh'
    elif now <= stale_deadline:
        state = 'stale'
    else:
        state = 'expired'
    return SnapshotResult(context, snapshot, state, now > expires_at)


def mark_snapshot_pending(
    *,
    cluster_id: str,
    dataset_key: str,
    parameters: dict[str, Any] | None,
    job_execution_id: int | None,
) -> AnalyticsSnapshot:
    normalized = canonical_parameters(dataset_key, parameters)
    fingerprint = parameter_fingerprint(normalized)
    snapshot = AnalyticsSnapshot.query.filter_by(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameter_fingerprint=fingerprint,
    ).first()
    if snapshot is None:
        snapshot = AnalyticsSnapshot()
        snapshot.cluster_id = cluster_id
        snapshot.dataset_key = dataset_key
        snapshot.parameter_fingerprint = fingerprint
        snapshot.parameters_json = normalized
        db.session.add(snapshot)
    snapshot.status = 'pending'
    snapshot.last_attempt_at = utcnow()
    snapshot.last_job_execution_id = job_execution_id
    snapshot.last_error = None
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        snapshot = AnalyticsSnapshot.query.filter_by(
            cluster_id=cluster_id,
            dataset_key=dataset_key,
            parameter_fingerprint=fingerprint,
        ).one()
    return snapshot


def store_snapshot(
    *,
    cluster_id: str,
    dataset_key: str,
    parameters: dict[str, Any] | None,
    context: dict[str, Any],
    job_execution_id: int | None,
    freshness_minutes: int | None = None,
    stale_grace_minutes: int | None = None,
) -> AnalyticsSnapshot:
    if context.get('dependency_blocker'):
        raise ValueError(f'Analytics snapshot {dataset_key} contains a dependency blocker and cannot be committed.')
    dataset = get_dataset(dataset_key)
    now = utcnow()
    snapshot = mark_snapshot_pending(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
        job_execution_id=job_execution_id,
    )
    snapshot.payload_json = encode_value(context)
    snapshot.status = 'ready'
    snapshot.generated_at = now
    snapshot.freshness_minutes = int(freshness_minutes or dataset.freshness_minutes)
    snapshot.stale_grace_minutes = int(stale_grace_minutes or dataset.stale_grace_minutes)
    snapshot.expires_at = now + timedelta(minutes=snapshot.freshness_minutes)
    snapshot.last_attempt_at = now
    snapshot.last_error = None
    snapshot.last_job_execution_id = job_execution_id
    db.session.commit()
    return snapshot


def fail_snapshot(
    *,
    cluster_id: str,
    dataset_key: str,
    parameters: dict[str, Any] | None,
    error: Exception | str,
    job_execution_id: int | None,
) -> None:
    snapshot = mark_snapshot_pending(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
        job_execution_id=job_execution_id,
    )
    snapshot.status = 'failed'
    snapshot.last_error = str(error)[:4000]
    snapshot.last_attempt_at = utcnow()
    db.session.commit()
