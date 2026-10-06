from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app

from app.extensions.db import db
from app.models.analytics import AnalyticsSnapshot
from app.platform_operations.data_lifecycle.retention.policy_service import resolve_policy
from app.platform_operations.data_lifecycle.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy


class AnalyticsSnapshotArchiveDomain:
    """Archive analytics materialization snapshots only after they are no longer serveable."""

    name = 'analytics_snapshot'
    source_model = 'analytics_snapshots'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        fallback = RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('ANALYTICS_SNAPSHOT_RETENTION_ENABLED', True),
            retention_days=_positive_int_config('ANALYTICS_SNAPSHOT_RETENTION_DAYS', 30),
            archive_retention_days=_positive_int_config('ANALYTICS_SNAPSHOT_ARCHIVE_RETENTION_DAYS', 180),
            batch_size=max(100, min(_positive_int_config('ANALYTICS_SNAPSHOT_RETENTION_BATCH_SIZE', 5000), 25000)),
            settings={
                'preserve_dataset_identity': True,
                'preserve_materialized_payload': True,
                'cleanup_only_after_stale_grace': True,
            },
        )
        return resolve_policy(self.name, fallback)

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        cutoff_at = now - timedelta(days=policy.retention_days)
        record_count = 0
        protected_count = 0
        maximum_record_id: int | None = None
        range_start: datetime | None = None
        range_end: datetime | None = None

        rows = (
            AnalyticsSnapshot.query.filter(
                AnalyticsSnapshot.status != 'pending',
                AnalyticsSnapshot.updated_at < cutoff_at,
            )
            .order_by(AnalyticsSnapshot.id.asc())
            .yield_per(policy.batch_size)
        )
        for row in rows:
            if not _eligible_for_boundary(row, cutoff_at=cutoff_at):
                protected_count += 1
                continue
            record_count += 1
            maximum_record_id = row.id
            updated_at = _as_utc(row.updated_at)
            if updated_at is not None:
                range_start = updated_at if range_start is None else min(range_start, updated_at)
                range_end = updated_at if range_end is None else max(range_end, updated_at)

        return ArchiveBoundary(
            selected_at=now,
            cutoff_at=cutoff_at,
            maximum_record_id=maximum_record_id,
            record_count=record_count,
            range_start=range_start,
            range_end=range_end,
            protected_record_count=protected_count,
        )

    def iter_records(self, boundary: ArchiveBoundary, policy: RetentionPolicy) -> Iterator[dict[str, Any]]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return
        last_id = 0
        while True:
            rows = (
                AnalyticsSnapshot.query.filter(
                    AnalyticsSnapshot.id <= boundary.maximum_record_id,
                    AnalyticsSnapshot.id > last_id,
                    AnalyticsSnapshot.status != 'pending',
                    AnalyticsSnapshot.updated_at < boundary.cutoff_at,
                )
                .order_by(AnalyticsSnapshot.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            for row in rows:
                last_id = row.id
                if _eligible_for_boundary(row, cutoff_at=boundary.cutoff_at):
                    yield self._serialize(row)
            db.session.expire_all()

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        cutoff_at = datetime.now(UTC) - timedelta(days=policy.retention_days)
        deleted_total = 0
        batch: list[int] = []
        try:
            for record_id in record_ids:
                batch.append(int(record_id))
                if len(batch) >= policy.batch_size:
                    deleted_total += self._delete_safe_batch(batch, cutoff_at=cutoff_at)
                    batch = []
            if batch:
                deleted_total += self._delete_safe_batch(batch, cutoff_at=cutoff_at)
        except Exception as exc:
            db.session.rollback()
            raise PartialCleanupError(
                'Analytics snapshot cleanup stopped after one or more committed batches.',
                deleted_total,
            ) from exc
        return deleted_total

    @staticmethod
    def _delete_safe_batch(record_ids: list[int], *, cutoff_at: datetime) -> int:
        rows = AnalyticsSnapshot.query.filter(AnalyticsSnapshot.id.in_(record_ids)).all()
        safe_ids = [row.id for row in rows if _eligible_for_boundary(row, cutoff_at=cutoff_at)]
        if not safe_ids:
            return 0
        deleted = AnalyticsSnapshot.query.filter(AnalyticsSnapshot.id.in_(safe_ids)).delete(synchronize_session=False)
        db.session.commit()
        return int(deleted or 0)

    def _serialize(self, row: AnalyticsSnapshot) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {
                'model': self.source_model,
                'record_id': row.id,
                'cluster_id': row.cluster_id,
            },
            'snapshot': {
                'dataset_key': row.dataset_key,
                'parameter_fingerprint': row.parameter_fingerprint,
                'parameters': row.parameters_json,
                'payload': row.payload_json,
                'status': row.status,
                'generated_at': _isoformat(row.generated_at),
                'expires_at': _isoformat(row.expires_at),
                'freshness_minutes': row.freshness_minutes,
                'stale_grace_minutes': row.stale_grace_minutes,
                'last_attempt_at': _isoformat(row.last_attempt_at),
                'last_error': row.last_error,
                'last_job_execution_id': row.last_job_execution_id,
                'created_at': _isoformat(row.created_at),
                'updated_at': _isoformat(row.updated_at),
            },
        }


def _eligible_for_boundary(snapshot: AnalyticsSnapshot, *, cutoff_at: datetime) -> bool:
    """Return True only when the snapshot is old and outside its serveable stale window.

    The stale-deadline comparison is anchored to the frozen retention cutoff, so
    inspect/write use the same deterministic boundary. Cleanup re-evaluates the
    current row before deletion so a concurrently refreshed snapshot is preserved.
    """

    if snapshot.status == 'pending':
        return False
    updated_at = _as_utc(snapshot.updated_at)
    if updated_at is None or updated_at >= cutoff_at:
        return False

    if snapshot.payload_json is None or snapshot.generated_at is None:
        return True

    generated_at = _as_utc(snapshot.generated_at)
    if generated_at is None:
        return True
    expires_at = _as_utc(snapshot.expires_at) or (
        generated_at + timedelta(minutes=max(int(snapshot.freshness_minutes or 0), 0))
    )
    stale_deadline = expires_at + timedelta(minutes=max(int(snapshot.stale_grace_minutes or 0), 0))
    return stale_deadline < cutoff_at


def _positive_int_config(key: str, default: int) -> int:
    try:
        return max(int(current_app.config.get(key, default)), 1)
    except (TypeError, ValueError):
        return default


def _bool_config(key: str, default: bool) -> bool:
    value = current_app.config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None
