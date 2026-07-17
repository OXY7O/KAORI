from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User
from app.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy


class OperationalActivityArchiveDomain:
    name = 'operational_activity'
    source_model = 'notifications'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        retention_days = _positive_int_config('ACTIVITY_RETENTION_DAYS', 90)
        archive_retention_days = _positive_int_config('ACTIVITY_ARCHIVE_RETENTION_DAYS', 365)
        batch_size = max(100, min(_positive_int_config('ACTIVITY_RETENTION_BATCH_SIZE', 5000), 25000))
        protect_unreviewed = _bool_config('ACTIVITY_RETENTION_PROTECT_UNREVIEWED', False)
        protected_max_days = _positive_int_config('ACTIVITY_RETENTION_PROTECTED_MAX_DAYS', 180)
        protected_max_days = max(protected_max_days, retention_days)

        return RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('ACTIVITY_RETENTION_ENABLED', True),
            retention_days=retention_days,
            archive_retention_days=archive_retention_days,
            batch_size=batch_size,
            protect_unreviewed=protect_unreviewed,
            protected_max_days=protected_max_days,
        )

    def inspect_boundary(
        self,
        policy: RetentionPolicy,
    ) -> ArchiveBoundary:
        now = datetime.now(UTC)
        cutoff_at = now - timedelta(days=policy.retention_days)
        protected_cutoff_at = (
            now - timedelta(days=policy.protected_max_days or policy.retention_days)
            if policy.protect_unreviewed
            else None
        )
        eligible_filter = self._eligible_filter(
            policy,
            cutoff_at=cutoff_at,
            protected_cutoff_at=protected_cutoff_at,
        )

        record_count, maximum_record_id, range_start, range_end = (
            db.session.query(
                func.count(Notification.id),
                func.max(Notification.id),
                func.min(Notification.created_at),
                func.max(Notification.created_at),
            )
            .filter(eligible_filter)
            .one()
        )

        protected_record_count = 0
        if policy.protect_unreviewed and protected_cutoff_at is not None:
            protected_record_count = Notification.query.filter(
                Notification.created_at < cutoff_at,
                Notification.created_at >= protected_cutoff_at,
                Notification.read_at.is_(None),
            ).count()

        return ArchiveBoundary(
            cutoff_at=cutoff_at,
            maximum_record_id=int(maximum_record_id) if maximum_record_id is not None else None,
            record_count=int(record_count or 0),
            range_start=_as_utc(range_start),
            range_end=_as_utc(range_end),
            protected_record_count=int(protected_record_count or 0),
            protected_cutoff_at=protected_cutoff_at,
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
                db.session.query(Notification, User)
                .outerjoin(User, User.id == Notification.user_id)
                .filter(
                    self._eligible_filter(
                        policy,
                        cutoff_at=boundary.cutoff_at,
                        protected_cutoff_at=boundary.protected_cutoff_at,
                    ),
                    Notification.id <= boundary.maximum_record_id,
                    Notification.id > last_id,
                )
                .order_by(Notification.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break

            for notification, user in rows:
                last_id = notification.id
                yield self._serialize(notification, user)

            db.session.expire_all()

    def cleanup_records(
        self,
        record_ids: Iterable[Any],
        policy: RetentionPolicy,
    ) -> int:
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
                'Operational activity cleanup stopped after one or more committed batches.',
                deleted_total,
            ) from exc

        return deleted_total

    @staticmethod
    def _delete_id_batch(record_ids: list[int]) -> int:
        deleted = Notification.query.filter(Notification.id.in_(record_ids)).delete(synchronize_session=False)
        db.session.commit()
        return int(deleted or 0)

    def _eligible_filter(
        self,
        policy: RetentionPolicy,
        *,
        cutoff_at: datetime,
        protected_cutoff_at: datetime | None = None,
    ):
        base_filter = Notification.created_at < cutoff_at
        if not policy.protect_unreviewed:
            return base_filter

        protected_cutoff = protected_cutoff_at or (
            datetime.now(UTC) - timedelta(days=policy.protected_max_days or policy.retention_days)
        )
        return and_(
            base_filter,
            or_(
                Notification.read_at.is_not(None),
                Notification.created_at < protected_cutoff,
            ),
        )

    def _serialize(
        self,
        notification: Notification,
        user: User | None,
    ) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {
                'model': self.source_model,
                'record_id': notification.id,
            },
            'activity': {
                'user_id': notification.user_id,
                'event_type': notification.event_type,
                'status': notification.status,
                'title': notification.title,
                'message': notification.message,
                'detail': notification.detail,
                'action_url': notification.action_url,
                'metadata': notification.metadata_json,
                'created_at': _isoformat(notification.created_at),
                'read_at': _isoformat(notification.read_at),
            },
            'actor_snapshot': {
                'user_id': user.id if user is not None else notification.user_id,
                'username': (user.username if user is not None else (notification.metadata_json or {}).get('username')),
                'email': (user.email if user is not None else (notification.metadata_json or {}).get('actor_email')),
                'display_name': (
                    user.display_name
                    if user is not None
                    else (notification.metadata_json or {}).get('actor_display_name')
                ),
                'auth_source': (
                    user.auth_source if user is not None else (notification.metadata_json or {}).get('auth_source')
                ),
                'deleted_at': _isoformat(user.deleted_at) if user is not None else None,
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
