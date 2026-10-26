from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func

from app.extensions.db import db
from app.models.notification_channel import NotificationDelivery
from app.platform_operations.data_lifecycle.retention.policy_service import resolve_policy
from app.platform_operations.data_lifecycle.retention.types import ArchiveBoundary, RetentionPolicy


class NotificationDeliveryArchiveDomain:
    """Non-destructive, provider-neutral delivery evidence archive.

    Until durable idempotency and all-time aggregates are admitted, source rows
    must stay in PostgreSQL. Never export the payload/replay envelope: it can
    contain encrypted transport credentials and potentially sensitive content.
    """

    name = 'notification_delivery'
    source_model = 'notification_deliveries'
    schema_version = 1
    cleanup_supported = False

    def build_policy(self) -> RetentionPolicy:
        return resolve_policy(
            self.name,
            RetentionPolicy(
                domain=self.name,
                enabled=False,
                retention_days=90,
                archive_retention_days=365,
                batch_size=1000,
                settings={
                    'archive_only': True,
                    'exclude_active_retries': True,
                    'omit_payload_and_replay': True,
                    'retain_hot_deduplication': True,
                },
            ),
        )

    @staticmethod
    def _eligible(cutoff_at: datetime):
        # Failed deliveries may still be retried; queued delivery is in-flight.
        # Both creation and last mutation must be outside the hot window.
        return (
            NotificationDelivery.status.in_(('sent', 'skipped')),
            NotificationDelivery.created_at < cutoff_at,
            NotificationDelivery.updated_at < cutoff_at,
        )

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        cutoff_at = now - timedelta(days=policy.retention_days)
        count, maximum_id, first_seen, last_seen = (
            db.session.query(
                func.count(NotificationDelivery.id),
                func.max(NotificationDelivery.id),
                func.min(NotificationDelivery.created_at),
                func.max(NotificationDelivery.created_at),
            )
            .filter(*self._eligible(cutoff_at))
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
                NotificationDelivery.query.filter(
                    *self._eligible(boundary.cutoff_at),
                    NotificationDelivery.id <= boundary.maximum_record_id,
                    NotificationDelivery.id > last_id,
                )
                .order_by(NotificationDelivery.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            for row in rows:
                last_id = row.id
                yield {
                    'schema_version': self.schema_version,
                    'domain': self.name,
                    'source': {
                        'model': self.source_model,
                        'record_id': row.id,
                        'channel_id': row.channel_id,
                    },
                    'evidence': {
                        'event_key': row.event_key,
                        'event_type': row.event_type,
                        'domain': row.domain,
                        'asset_type': row.asset_type,
                        'asset_key': row.asset_key,
                        'severity': row.severity,
                        'status': row.status,
                        'attempt_count': row.attempt_count,
                        'provider_message_id': row.provider_message_id,
                        'created_at': _isoformat(row.created_at),
                        'updated_at': _isoformat(row.updated_at),
                        'sent_at': _isoformat(row.sent_at),
                    },
                }
            db.session.expire_all()

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        # Defense in depth: even direct calls must never erase hot evidence.
        raise RuntimeError(
            'Notification Delivery cleanup is blocked until durable deduplication, '
            'historical aggregates, and channel dependencies are admitted.'
        )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _isoformat(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None
