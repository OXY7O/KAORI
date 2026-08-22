from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.alert_ops import AlertCase, AlertCaseEvent, AlertSilence
from app.models.notification_channel import NotificationDelivery
from app.platform_operations.data_lifecycle.retention.policy_service import resolve_policy
from app.platform_operations.data_lifecycle.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy


class AlertIncidentArchiveDomain:
    """Archive closed Alert Operations evidence while preserving a searchable case index."""

    name = 'alert_incident'
    source_model = 'alert_cases'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        fallback = RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('ALERT_INCIDENT_RETENTION_ENABLED', True),
            retention_days=_positive_int_config('ALERT_INCIDENT_RETENTION_DAYS', 90),
            archive_retention_days=_positive_int_config('ALERT_INCIDENT_ARCHIVE_RETENTION_DAYS', 730),
            batch_size=max(100, min(_positive_int_config('ALERT_INCIDENT_RETENTION_BATCH_SIZE', 1000), 10000)),
            settings={
                'closed_cases_only': True,
                'preserve_searchable_case_index': True,
                'archive_timeline': True,
                'archive_notification_delivery': True,
                'archive_postmortem': True,
            },
        )
        return resolve_policy(self.name, fallback)

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        cutoff_at = now - timedelta(days=policy.retention_days)
        count, maximum_id, range_start, range_end = (
            db.session.query(
                func.count(AlertCase.id),
                func.max(AlertCase.id),
                func.min(AlertCase.closed_at),
                func.max(AlertCase.closed_at),
            )
            .filter(
                AlertCase.workflow_state == 'closed',
                AlertCase.closed_at.is_not(None),
                AlertCase.closed_at < cutoff_at,
                AlertCase.archive_compacted_at.is_(None),
            )
            .one()
        )
        return ArchiveBoundary(
            selected_at=now,
            cutoff_at=cutoff_at,
            maximum_record_id=int(maximum_id) if maximum_id is not None else None,
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
                AlertCase.query.filter(
                    AlertCase.id <= boundary.maximum_record_id,
                    AlertCase.id > last_id,
                    AlertCase.workflow_state == 'closed',
                    AlertCase.closed_at.is_not(None),
                    AlertCase.closed_at < boundary.cutoff_at,
                    AlertCase.archive_compacted_at.is_(None),
                )
                .order_by(AlertCase.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            for case in rows:
                last_id = case.id
                yield self._serialize(case)
            db.session.expire_all()

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        cutoff_at = datetime.now(UTC) - timedelta(days=policy.retention_days)
        cleaned = 0
        try:
            for raw_id in record_ids:
                case = db.session.get(AlertCase, int(raw_id))
                if (
                    case is None
                    or case.workflow_state != 'closed'
                    or case.closed_at is None
                    or case.closed_at >= cutoff_at
                ):
                    continue
                AlertCaseEvent.query.filter_by(case_id=case.id).delete(synchronize_session=False)
                AlertSilence.query.filter_by(case_id=case.id).delete(synchronize_session=False)
                NotificationDelivery.query.filter(
                    NotificationDelivery.event_key.like(f'alert-case:{case.public_id}:%')
                ).delete(synchronize_session=False)
                case.labels_json = {}
                case.evidence_json = {}
                case.postmortem_json = {}
                case.remediation_steps_json = []
                case.archive_compacted_at = datetime.now(UTC)
                cleaned += 1
                if cleaned % policy.batch_size == 0:
                    db.session.commit()
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise PartialCleanupError(
                'Alert incident cleanup stopped after one or more committed batches.',
                cleaned,
            ) from exc
        return cleaned

    def _serialize(self, case: AlertCase) -> dict[str, Any]:
        timeline = [
            {
                'event_type': event.event_type,
                'actor_user_id': event.actor_user_id,
                'summary': event.summary,
                'metadata': event.metadata_json,
                'created_at': _isoformat(event.created_at),
            }
            for event in AlertCaseEvent.query.filter_by(case_id=case.id).order_by(AlertCaseEvent.created_at.asc()).all()
        ]
        silences = [
            {
                'starts_at': _isoformat(row.starts_at),
                'ends_at': _isoformat(row.ends_at),
                'reason': row.reason,
                'created_by_user_id': row.created_by_user_id,
                'revoked_at': _isoformat(row.revoked_at),
                'revoked_by_user_id': row.revoked_by_user_id,
            }
            for row in AlertSilence.query.filter_by(case_id=case.id).order_by(AlertSilence.created_at.asc()).all()
        ]
        deliveries = [
            {
                'channel_id': row.channel_id,
                'event_type': row.event_type,
                'status': row.status,
                'attempt_count': row.attempt_count,
                'provider_message_id': row.provider_message_id,
                'error_message': row.error_message,
                'created_at': _isoformat(row.created_at),
                'sent_at': _isoformat(row.sent_at),
            }
            for row in NotificationDelivery.query.filter(
                NotificationDelivery.event_key.like(f'alert-case:{case.public_id}:%')
            )
            .order_by(NotificationDelivery.created_at.asc())
            .all()
        ]
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {'model': self.source_model, 'record_id': case.id, 'case_id': case.public_id},
            'incident': {
                'case_id': case.public_id,
                'alert_name': case.alert_name,
                'severity': case.severity,
                'domain': case.domain,
                'asset_type': case.asset_type,
                'asset_key': case.asset_key,
                'asset_name': case.asset_name,
                'summary': case.summary,
                'target': case.target,
                'namespace': case.namespace,
                'labels': case.labels_json,
                'evidence': case.evidence_json,
                'first_seen_at': _isoformat(case.first_seen_at),
                'source_resolved_at': _isoformat(case.source_resolved_at),
                'closed_at': _isoformat(case.closed_at),
                'owner_user_id': case.owner_user_id,
                'resolution_summary': case.resolution_summary,
                'remediation_steps': case.remediation_steps_json,
                'verification_evidence': case.verification_evidence,
                'change_reference': case.change_reference,
                'ticket_reference': case.ticket_reference,
                'postmortem_required': case.postmortem_required,
                'postmortem_status': case.postmortem_status,
                'postmortem': case.postmortem_json,
            },
            'timeline': timeline,
            'silences': silences,
            'notification_deliveries': deliveries,
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
