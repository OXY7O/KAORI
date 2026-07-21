from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.runtime import IntegrationRuntimeObservation
from app.retention.policy_service import resolve_policy
from app.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy


class RuntimeObservationArchiveDomain:
    """Archive provider runtime evidence without imposing a write-time row cap."""

    name = 'runtime_observation'
    source_model = 'integration_runtime_observations'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        fallback = RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('RUNTIME_OBSERVATION_RETENTION_ENABLED', True),
            retention_days=_positive_int_config('RUNTIME_OBSERVATION_RETENTION_DAYS', 90),
            archive_retention_days=_positive_int_config('RUNTIME_OBSERVATION_ARCHIVE_RETENTION_DAYS', 365),
            batch_size=max(100, min(_positive_int_config('RUNTIME_OBSERVATION_RETENTION_BATCH_SIZE', 5000), 25000)),
            settings={
                'preserve_provider_identity': True,
                'preserve_capability_evidence': True,
            },
        )
        return resolve_policy(self.name, fallback)

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        cutoff_at = datetime.now(UTC) - timedelta(days=policy.retention_days)
        count, max_id, range_start, range_end = (
            db.session.query(
                func.count(IntegrationRuntimeObservation.id),
                func.max(IntegrationRuntimeObservation.id),
                func.min(IntegrationRuntimeObservation.observed_at),
                func.max(IntegrationRuntimeObservation.observed_at),
            )
            .filter(IntegrationRuntimeObservation.observed_at < cutoff_at)
            .one()
        )
        return ArchiveBoundary(
            cutoff_at=cutoff_at,
            maximum_record_id=int(max_id) if max_id is not None else None,
            record_count=int(count or 0),
            range_start=_as_utc(range_start),
            range_end=_as_utc(range_end),
        )

    def iter_records(self, boundary: ArchiveBoundary, policy: RetentionPolicy) -> Iterator[dict[str, Any]]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return
        last_id = 0
        while True:
            rows = (
                IntegrationRuntimeObservation.query.filter(
                    IntegrationRuntimeObservation.observed_at < boundary.cutoff_at,
                    IntegrationRuntimeObservation.id <= boundary.maximum_record_id,
                    IntegrationRuntimeObservation.id > last_id,
                )
                .order_by(IntegrationRuntimeObservation.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            for row in rows:
                last_id = row.id
                yield self._serialize(row)
            db.session.expire_all()

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        deleted_total = 0
        batch: list[int] = []
        try:
            for record_id in record_ids:
                batch.append(int(record_id))
                if len(batch) >= policy.batch_size:
                    deleted_total += self._delete_id_batch(batch)
                    batch = []
            if batch:
                deleted_total += self._delete_id_batch(batch)
        except Exception as exc:
            db.session.rollback()
            raise PartialCleanupError(
                'Runtime observation cleanup stopped after one or more committed batches.',
                deleted_total,
            ) from exc
        return deleted_total

    @staticmethod
    def _delete_id_batch(record_ids: list[int]) -> int:
        deleted = IntegrationRuntimeObservation.query.filter(
            IntegrationRuntimeObservation.id.in_(record_ids),
        ).delete(synchronize_session=False)
        db.session.commit()
        return int(deleted or 0)

    def _serialize(self, row: IntegrationRuntimeObservation) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {
                'model': self.source_model,
                'record_id': row.id,
                'integration_instance_id': row.integration_instance_id,
            },
            'observation': {
                'provider': row.provider,
                'instance_id': row.instance_id,
                'instance_name': row.instance_name,
                'trigger_type': row.trigger_type,
                'readiness': row.readiness,
                'health_status': row.health_status,
                'health_score': row.health_score,
                'latency_ms': row.latency_ms,
                'compatibility_profile': row.compatibility_profile,
                'capability_profile': row.capability_profile,
                'capability_snapshot': row.capability_snapshot,
                'diagnostics': row.diagnostics,
                'message': row.message,
                'observed_at': _isoformat(row.observed_at),
                'created_at': _isoformat(row.created_at),
            },
        }


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
