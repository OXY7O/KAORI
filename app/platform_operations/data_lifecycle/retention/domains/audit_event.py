"""Minimal, paused-by-default AuditEvent archive projection (#2890).

The original AuditEvent remains authoritative in hot PostgreSQL. This
adapter intentionally omits free-form metadata, network identifiers, and
actor reconstruction until producer-by-producer security/retention authority
(#2891) and verified compaction (#2892) have been admitted.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func

from app.extensions.db import db
from app.models.audit import AuditEvent
from app.platform_operations.data_lifecycle.retention.policy_service import resolve_policy
from app.platform_operations.data_lifecycle.retention.types import ArchiveBoundary, RetentionPolicy
from app.platform_operations.notifications.metadata import redact_operational_text


class AuditEventArchiveDomain:
    name = 'audit_event'
    source_model = 'audit_events'
    schema_version = 1
    cleanup_supported = False

    def build_policy(self) -> RetentionPolicy:
        # Proposed defaults for explicit policy review, not a retention mandate.
        # An unpersisted policy is refused by the shared execution admission.
        return resolve_policy(
            self.name,
            RetentionPolicy(
                domain=self.name,
                enabled=False,
                retention_days=365,
                archive_retention_days=3650,
                batch_size=250,
                settings={
                    'archive_only': True,
                    'manual_execution_only': True,
                    'minimal_redacted_evidence': True,
                    'omit_freeform_metadata': True,
                    'hot_source_authoritative': True,
                },
            ),
        )

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        cutoff_at = now - timedelta(days=policy.retention_days)
        count, maximum_id, first_seen, last_seen = (
            db.session.query(
                func.count(AuditEvent.id),
                func.max(AuditEvent.id),
                func.min(AuditEvent.created_at),
                func.max(AuditEvent.created_at),
            )
            .filter(AuditEvent.created_at < cutoff_at)
            .one()
        )
        return ArchiveBoundary(
            selected_at=now,
            cutoff_at=cutoff_at,
            maximum_record_id=int(maximum_id) if maximum_id is not None else None,
            record_count=int(count or 0),
            range_start=_as_utc(first_seen),
            range_end=_as_utc(last_seen),
        )

    def iter_records(
        self,
        boundary: ArchiveBoundary,
        policy: RetentionPolicy,
    ) -> Iterator[dict[str, Any]]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return
        last_id = 0
        while True:
            rows = (
                AuditEvent.query.filter(
                    AuditEvent.created_at < boundary.cutoff_at,
                    AuditEvent.id <= boundary.maximum_record_id,
                    AuditEvent.id > last_id,
                )
                .order_by(AuditEvent.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            for event in rows:
                last_id = event.id
                yield self._serialize(event)
            db.session.expire_all()

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        # Defense in depth, including direct adapter callers.
        raise RuntimeError(
            'AuditEvent hot cleanup is not admitted: source-specific retention, '
            'identity, dependencies, legal holds and archive access require review.'
        )

    def _serialize(self, event: AuditEvent) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {
                'model': self.source_model,
                'record_id': event.id,
            },
            'evidence': {
                'actor_user_id': event.actor_user_id,
                'actor_identity_is_snapshot': False,
                'target_type': redact_operational_text(event.target_type, limit=80),
                'target_id': (
                    redact_operational_text(event.target_id, limit=120) if event.target_id is not None else None
                ),
                'action': redact_operational_text(event.action, limit=120),
                'summary': redact_operational_text(event.summary, limit=255),
                'created_at': _isoformat(event.created_at),
                'freeform_metadata_included': False,
                'source_permissions_preserved': True,
            },
        }


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _isoformat(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None
