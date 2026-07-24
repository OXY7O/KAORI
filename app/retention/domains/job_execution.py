from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import and_, func, or_

from app.extensions.db import db
from app.models.job import JobExecution, JobExecutionSubscriber
from app.models.user import User
from app.retention.policy_service import resolve_policy
from app.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy

TERMINAL_STATUSES = ('succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired')


class JobExecutionArchiveDomain:
    name = 'job_execution'
    source_model = 'job_executions'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        retention_days = _positive_int_config('JOB_EXECUTION_RETENTION_DAYS', 90)
        fallback = RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('JOB_EXECUTION_RETENTION_ENABLED', True),
            retention_days=retention_days,
            archive_retention_days=_positive_int_config('JOB_EXECUTION_ARCHIVE_RETENTION_DAYS', 365),
            batch_size=max(100, min(_positive_int_config('JOB_EXECUTION_RETENTION_BATCH_SIZE', 2500), 25000)),
            settings={
                'workload_retention_days': {
                    'runtime': _positive_int_config('JOB_EXECUTION_RUNTIME_RETENTION_DAYS', 30),
                    'validation': _positive_int_config('JOB_EXECUTION_VALIDATION_RETENTION_DAYS', 30),
                    'analytics': _positive_int_config('JOB_EXECUTION_ANALYTICS_RETENTION_DAYS', 90),
                    'forecasting': _positive_int_config('JOB_EXECUTION_FORECASTING_RETENTION_DAYS', 180),
                    'standard': retention_days,
                },
                'failed_retention_days': _positive_int_config('JOB_EXECUTION_FAILED_RETENTION_DAYS', 90),
                'preserve_result_references': True,
            },
        )
        return resolve_policy(self.name, fallback)

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        eligible = self._eligible_filter(policy, now=now)
        count, max_id, range_start, range_end = (
            db.session.query(
                func.count(JobExecution.id),
                func.max(JobExecution.id),
                func.min(JobExecution.completed_at),
                func.max(JobExecution.completed_at),
            )
            .filter(eligible)
            .one()
        )
        return ArchiveBoundary(
            cutoff_at=now - timedelta(days=policy.retention_days),
            maximum_record_id=int(max_id) if max_id is not None else None,
            record_count=int(count or 0),
            range_start=_as_utc(range_start),
            range_end=_as_utc(range_end),
        )

    def iter_records(self, boundary: ArchiveBoundary, policy: RetentionPolicy) -> Iterator[dict[str, Any]]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return
        last_id = 0
        now = datetime.now(UTC)
        while True:
            rows = (
                JobExecution.query.filter(
                    self._eligible_filter(policy, now=now),
                    JobExecution.id <= boundary.maximum_record_id,
                    JobExecution.id > last_id,
                )
                .order_by(JobExecution.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            job_ids = [item.id for item in rows]
            subscriber_rows = (
                db.session.query(JobExecutionSubscriber, User)
                .outerjoin(User, User.id == JobExecutionSubscriber.user_id)
                .filter(JobExecutionSubscriber.job_execution_id.in_(job_ids))
                .order_by(JobExecutionSubscriber.job_execution_id, JobExecutionSubscriber.id)
                .all()
            )
            subscribers: dict[int, list[dict[str, Any]]] = {job_id: [] for job_id in job_ids}
            for subscriber, user in subscriber_rows:
                subscribers.setdefault(subscriber.job_execution_id, []).append(
                    {
                        'user_id': subscriber.user_id,
                        'username': user.username if user is not None else None,
                        'display_name': user.display_name if user is not None else None,
                        'notify_on_completion': subscriber.notify_on_completion,
                        'subscribed_at': _isoformat(subscriber.subscribed_at),
                        'last_seen_at': _isoformat(subscriber.last_seen_at),
                    }
                )
            for job in rows:
                last_id = job.id
                yield self._serialize(job, subscribers.get(job.id, []))
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
                'Job execution cleanup stopped after one or more committed batches.',
                deleted_total,
            ) from exc
        return deleted_total

    @staticmethod
    def _delete_id_batch(record_ids: list[int]) -> int:
        # Database FKs preserve child-job history by setting parent_job_id to NULL,
        # while subscribers are deleted with the archived execution record.
        deleted = JobExecution.query.filter(
            JobExecution.id.in_(record_ids),
            JobExecution.status.in_(TERMINAL_STATUSES),
            JobExecution.active_deduplication_key.is_(None),
        ).delete(synchronize_session=False)
        db.session.commit()
        return int(deleted or 0)

    def _eligible_filter(self, policy: RetentionPolicy, *, now: datetime):
        settings = policy.settings or {}
        workload_days = dict(settings.get('workload_retention_days') or {})
        failed_days = max(int(settings.get('failed_retention_days') or policy.retention_days), 1)
        retention_clauses = []
        for workload in ('runtime', 'validation', 'analytics', 'forecasting', 'standard'):
            days = max(int(workload_days.get(workload, policy.retention_days)), 1)
            retention_clauses.append(
                and_(
                    JobExecution.workload_class == workload,
                    JobExecution.completed_at < now - timedelta(days=days),
                )
            )
        retention_clauses.append(
            and_(
                ~JobExecution.workload_class.in_(tuple(workload_days.keys())),
                JobExecution.completed_at < now - timedelta(days=policy.retention_days),
            )
        )
        return and_(
            JobExecution.status.in_(TERMINAL_STATUSES),
            JobExecution.completed_at.is_not(None),
            JobExecution.active_deduplication_key.is_(None),
            or_(
                and_(JobExecution.status == 'failed', JobExecution.completed_at < now - timedelta(days=failed_days)),
                and_(JobExecution.status != 'failed', or_(*retention_clauses)),
            ),
        )

    def _serialize(self, job: JobExecution, subscribers: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {'model': self.source_model, 'record_id': job.id, 'public_id': job.public_id},
            'execution': {
                'job_type': job.job_type,
                'operation': job.operation,
                'workload_class': job.workload_class,
                'queue_name': job.queue_name,
                'priority': job.priority,
                'status': job.status,
                'requested_by_user_id': job.requested_by_user_id,
                'provider_type': job.provider_type,
                'provider_instance_id': job.provider_instance_id,
                'scope_type': job.scope_type,
                'scope_key': job.scope_key,
                'resource_group': job.resource_group,
                'deduplication_key': job.deduplication_key,
                'parameter_fingerprint': job.parameter_fingerprint,
                'payload': job.payload_json,
                'celery_task_id': job.celery_task_id,
                'parent_job_id': job.parent_job_id,
                'progress_current': job.progress_current,
                'progress_total': job.progress_total,
                'progress_message': job.progress_message,
                'attempt_count': job.attempt_count,
                'max_attempts': job.max_attempts,
                'error_code': job.error_code,
                'error_message': job.error_message,
                'result_type': job.result_type,
                # Result data is owned by its domain. Lifecycle cleanup removes only
                # execution metadata and never follows or deletes this reference.
                'result_reference': job.result_reference,
                'result_summary': job.result_summary_json,
                'queued_at': _isoformat(job.queued_at),
                'started_at': _isoformat(job.started_at),
                'heartbeat_at': _isoformat(job.heartbeat_at),
                'completed_at': _isoformat(job.completed_at),
                'cancel_requested_at': _isoformat(job.cancel_requested_at),
                'expires_at': _isoformat(job.expires_at),
                'created_at': _isoformat(job.created_at),
                'updated_at': _isoformat(job.updated_at),
            },
            'subscribers': subscribers,
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
