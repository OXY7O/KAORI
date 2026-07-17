from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task
from flask import current_app

from app.extensions import db
from app.models.archive import ArchiveArtifact
from app.models.user import User
from app.notifications.service import create_notification
from app.retention.domains import get_archive_domain
from app.retention.service import purge_expired_archives, run_retention_archive

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='app.retention.tasks.run_domain_retention',
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_domain_retention_task(
    self,
    *,
    domain_name: str,
    cleanup: bool,
    trigger_type: str = 'manual',
    requested_by_user_id: int | None = None,
) -> dict[str, Any]:
    operation_mode = 'archive_and_cleanup' if cleanup else 'archive_only'
    _record_retention_activity_event(
        requested_by_user_id=requested_by_user_id,
        trigger_type=trigger_type,
        event_type='operational_activity_retention_started',
        status='info',
        title='Activity retention started',
        message=(
            'The scheduled archive and cleanup lifecycle started in the background.'
            if cleanup and trigger_type == 'scheduled'
            else 'The scheduled archive lifecycle started in the background.'
            if trigger_type == 'scheduled'
            else 'The archive and cleanup lifecycle started in the background.'
            if cleanup
            else 'The archive lifecycle started in the background.'
        ),
        detail='KAORI will archive eligible operational activity, verify the stored artifacts, and perform cleanup only when verification succeeds.',
        metadata={
            'domain': domain_name,
            'task_id': self.request.id,
            'trigger_type': trigger_type,
            'operation_mode': operation_mode,
            'cleanup_requested': cleanup,
            'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE', 'inventory') or 'inventory'),
        },
    )

    try:
        result = run_retention_archive(
            domain_name=domain_name,
            trigger_type=trigger_type,
            cleanup=cleanup,
            triggered_by_user_id=requested_by_user_id,
            celery_task_id=self.request.id,
        )
        _notify_requester(
            user_id=requested_by_user_id,
            result=result,
            cleanup=cleanup,
        )
        _record_retention_completion(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
            cleanup=cleanup,
            task_id=self.request.id,
            result=result,
        )
        return result
    except Exception as exc:
        db.session.rollback()
        logger.exception('Retention task failed for %s.', domain_name)
        _notify_failure(
            user_id=requested_by_user_id,
            domain_name=domain_name,
            cleanup=cleanup,
            error=exc,
        )
        _record_retention_failure(
            requested_by_user_id=requested_by_user_id,
            domain_name=domain_name,
            trigger_type=trigger_type,
            cleanup=cleanup,
            task_id=self.request.id,
            error=exc,
        )
        raise


@shared_task(
    bind=True,
    name='app.retention.tasks.run_scheduled_retention',
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_scheduled_retention_task(self) -> dict[str, Any]:
    configured_domains = current_app.config.get(
        'ARCHIVE_SCHEDULED_DOMAINS',
        ('operational_activity',),
    )
    if isinstance(configured_domains, str):
        configured_domains = tuple(
            item.strip().lower().replace('-', '_')
            for item in configured_domains.split(',')
            if item.strip()
        )

    results: dict[str, Any] = {}
    for domain_name in configured_domains:
        try:
            domain = get_archive_domain(domain_name)
            policy = domain.build_policy()
            if not policy.enabled:
                results[domain_name] = {'status': 'disabled'}
                continue

            _record_retention_activity_event(
                requested_by_user_id=None,
                trigger_type='scheduled',
                event_type='operational_activity_retention_started',
                status='info',
                title='Scheduled activity retention started',
                message='The automatic archive and cleanup lifecycle started in the background.',
                detail='KAORI will archive eligible activity records, verify the stored artifacts, and clean PostgreSQL only after verification succeeds.',
                metadata={
                    'domain': domain_name,
                    'task_id': self.request.id,
                    'trigger_type': 'scheduled',
                    'operation_mode': 'archive_and_cleanup',
                    'cleanup_requested': True,
                    'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE', 'inventory') or 'inventory'),
                },
            )

            retention_result = run_retention_archive(
                domain_name=domain_name,
                trigger_type='scheduled',
                cleanup=True,
                triggered_by_user_id=None,
                celery_task_id=self.request.id,
            )
            purge_result = purge_expired_archives(
                domain_name=domain_name,
                retention_days=policy.archive_retention_days,
                dry_run=False,
            )
            _record_retention_completion(
                requested_by_user_id=None,
                trigger_type='scheduled',
                cleanup=True,
                task_id=self.request.id,
                result=retention_result,
            )
            results[domain_name] = {
                'retention': retention_result,
                'archive_purge': purge_result,
            }
        except Exception as exc:
            db.session.rollback()
            logger.exception('Scheduled retention failed for %s.', domain_name)
            _record_retention_failure(
                requested_by_user_id=None,
                domain_name=domain_name,
                trigger_type='scheduled',
                cleanup=True,
                task_id=self.request.id,
                error=exc,
            )
            results[domain_name] = {
                'status': 'failed',
                'error_type': type(exc).__name__,
                'error': str(exc),
            }

    return {'domains': results}


def _notify_requester(
    *,
    user_id: int | None,
    result: dict[str, Any],
    cleanup: bool,
) -> None:
    if user_id is None:
        return

    if result.get('status') == 'no_data':
        title = 'Activity retention found no eligible records'
        message = 'No activity records were old enough to archive.'
        status = 'info'
    else:
        record_count = int(result.get('record_count') or 0)
        deleted_count = int(result.get('cleanup_deleted_count') or 0)
        title = 'Activity archive and cleanup completed' if cleanup else 'Activity archive completed'
        message = (
            f'{record_count} activity records were archived and {deleted_count} were removed from hot storage.'
            if cleanup
            else f'{record_count} activity records were archived without database cleanup.'
        )
        status = 'warning' if result.get('status') == 'cleanup_partial' else 'success'

    _safe_create_notification(
        user_id=user_id,
        status=status,
        title=title,
        message=message,
        detail='Review the Retention & Archive section for archive status, checksum, and download actions.',
        metadata={
            'archive_id': result.get('archive_id'),
            'record_count': result.get('record_count', 0),
            'cleanup_deleted_count': result.get('cleanup_deleted_count', 0),
            'storage_backend': result.get('storage_backend'),
        },
    )


def _notify_failure(
    *,
    user_id: int | None,
    domain_name: str,
    cleanup: bool,
    error: Exception,
) -> None:
    if user_id is None:
        return

    _safe_create_notification(
        user_id=user_id,
        status='error',
        title='Activity retention failed',
        message='The archive-first retention job stopped before it could complete safely.',
        detail='Database cleanup is blocked when archive creation or verification fails. Review the archive registry and worker logs.',
        metadata={
            'domain': domain_name,
            'cleanup_requested': cleanup,
            'error_type': type(error).__name__,
        },
    )


def _safe_create_notification(
    *,
    user_id: int,
    status: str,
    title: str,
    message: str,
    detail: str,
    metadata: dict[str, Any],
) -> None:
    try:
        create_notification(
            user_id=user_id,
            event_type='operational_activity_retention',
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url='/notifications/activity#activity-retention',
            metadata=metadata,
        )
    except Exception:
        db.session.rollback()
        logger.exception('Could not create the retention completion notification.')


def _record_retention_completion(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    cleanup: bool,
    task_id: str | None,
    result: dict[str, Any],
) -> None:
    operation_mode = 'archive_and_cleanup' if cleanup else 'archive_only'
    snapshot = _load_archive_snapshot(
        archive_id=str(result.get('archive_id') or '').strip() or None,
        task_id=task_id,
    )
    base_metadata: dict[str, Any] = {
        'domain': result.get('domain', 'operational_activity'),
        'task_id': task_id,
        'trigger_type': trigger_type,
        'operation_mode': operation_mode,
        'cleanup_requested': cleanup,
        'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE', 'inventory') or 'inventory'),
    }
    base_metadata.update(snapshot)

    status = str(result.get('status') or 'success')
    if status == 'no_data':
        _record_retention_activity_event(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
            event_type='operational_activity_retention_completed',
            status='info',
            title='Activity retention completed with no eligible records',
            message='No operational activity records crossed the hot-data retention boundary.',
            detail='No archive artifact was created because the retention boundary returned zero eligible records.',
            metadata=base_metadata,
        )
        return

    if status == 'cleanup_partial':
        record_count = int(result.get('record_count') or 0)
        deleted_count = int(result.get('cleanup_deleted_count') or 0)
        _record_retention_activity_event(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
            event_type='operational_activity_retention_completed',
            status='warning',
            title='Activity retention completed with cleanup review required',
            message=f'{record_count} records were archived, but cleanup removed only {deleted_count} records.',
            detail='The archive is valid and verified, but cleanup did not remove every expected record. Review the recorded metadata before retrying any cleanup action.',
            metadata={
                **base_metadata,
                'archive_status': status,
                'record_count': record_count,
                'cleanup_deleted_count': deleted_count,
                'result_reason': 'Cleanup deleted fewer rows than were archived.',
                'reason': snapshot.get('failure_summary') or 'Cleanup finished partially and requires operator review.',
                'error_message': snapshot.get('error_message'),
            },
        )
        return

    record_count = int(result.get('record_count') or 0)
    deleted_count = int(result.get('cleanup_deleted_count') or 0)
    _record_retention_activity_event(
        requested_by_user_id=requested_by_user_id,
        trigger_type=trigger_type,
        event_type='operational_activity_retention_completed',
        status='success',
        title='Activity retention completed',
        message=(
            f'{record_count} records were archived and {deleted_count} records were removed from PostgreSQL.'
            if cleanup
            else f'{record_count} records were archived without database cleanup.'
        ),
        detail='The activity archive completed and the recorded metadata includes the verification outcome, storage location, and retention boundary used by the job.',
        metadata={
            **base_metadata,
            'archive_status': status,
            'record_count': record_count,
            'cleanup_deleted_count': deleted_count,
        },
    )


def _record_retention_failure(
    *,
    requested_by_user_id: int | None,
    domain_name: str,
    trigger_type: str,
    cleanup: bool,
    task_id: str | None,
    error: Exception,
) -> None:
    snapshot = _load_archive_snapshot(task_id=task_id)
    operation_mode = 'archive_and_cleanup' if cleanup else 'archive_only'
    _record_retention_activity_event(
        requested_by_user_id=requested_by_user_id,
        trigger_type=trigger_type,
        event_type='operational_activity_retention_failed',
        status='error',
        title='Activity retention failed',
        message='The archive-first retention lifecycle stopped before it could complete safely.',
        detail='Cleanup remains protected. Review the captured metadata for the archive boundary, storage verification, and background task trace before retrying the job.',
        metadata={
            'domain': domain_name,
            'task_id': task_id,
            'trigger_type': trigger_type,
            'operation_mode': operation_mode,
            'cleanup_requested': cleanup,
            'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE', 'inventory') or 'inventory'),
            'error_type': type(error).__name__,
            'reason': _friendly_error_summary(str(error)),
            'error_message': snapshot.get('error_message') or f'{type(error).__name__}: {error}',
            **snapshot,
        },
    )


def _record_retention_activity_event(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str,
    metadata: dict[str, Any],
) -> None:
    user_id = _resolve_activity_owner_user_id(requested_by_user_id)
    if user_id is None:
        return

    payload = dict(metadata)
    if trigger_type == 'scheduled' and requested_by_user_id is None:
        payload.setdefault('actor_display_name', 'System scheduler')
        payload.setdefault('actor_role', 'Background worker')
        payload.setdefault('auth_source', 'system')
        payload.setdefault('actor_email', 'Automatic schedule')
    elif requested_by_user_id is not None:
        payload.setdefault('request_origin', 'Interactive action')

    try:
        create_notification(
            user_id=user_id,
            event_type=event_type,
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url='/notifications/activity#activity-retention',
            metadata=payload,
        )
    except Exception:
        db.session.rollback()
        logger.exception('Could not persist retention activity audit event %s.', event_type)


def _resolve_activity_owner_user_id(preferred_user_id: int | None) -> int | None:
    if preferred_user_id is not None:
        preferred_user = db.session.get(User, preferred_user_id)
        if preferred_user is not None and preferred_user.deleted_at is None and preferred_user.is_active:
            return preferred_user.id

    active_users = (
        User.query.filter(User.deleted_at.is_(None), User.account_is_active.is_(True))
        .order_by(User.is_super_admin.desc(), User.created_at.asc(), User.id.asc())
        .all()
    )
    for user in active_users:
        if user.is_admin_level:
            return user.id
    return active_users[0].id if active_users else None


def _load_archive_snapshot(
    *,
    archive_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    artifact: ArchiveArtifact | None = None
    if archive_id:
        artifact = db.session.get(ArchiveArtifact, archive_id)
    elif task_id:
        artifact = (
            ArchiveArtifact.query.filter(ArchiveArtifact.celery_task_id == task_id)
            .order_by(ArchiveArtifact.created_at.desc(), ArchiveArtifact.id.desc())
            .first()
        )

    if artifact is None:
        return {}

    metadata = artifact.metadata_json or {}
    return {
        'archive_id': artifact.id,
        'archive_status': artifact.status,
        'archive_format': artifact.archive_format,
        'compression': artifact.compression,
        'record_count': artifact.record_count,
        'cleanup_deleted_count': artifact.cleanup_deleted_count,
        'storage_backend': artifact.storage_backend,
        'data_object_key': artifact.data_object_key,
        'manifest_object_key': artifact.manifest_object_key,
        'data_uri': artifact.data_uri,
        'manifest_uri': artifact.manifest_uri,
        'size_bytes': artifact.size_bytes,
        'manifest_size_bytes': artifact.manifest_size_bytes,
        'checksum_sha256': artifact.checksum_sha256,
        'manifest_checksum_sha256': artifact.manifest_checksum_sha256,
        'cutoff_at': _isoformat(artifact.cutoff_at),
        'range_start': _isoformat(artifact.range_start),
        'range_end': _isoformat(artifact.range_end),
        'boundary_record_id': artifact.boundary_record_id,
        'protected_record_count': metadata.get('protected_record_count'),
        'protected_cutoff_at': metadata.get('protected_cutoff_at'),
        'archived_at': _isoformat(artifact.archived_at),
        'verified_at': _isoformat(artifact.verified_at),
        'cleanup_completed_at': _isoformat(artifact.cleanup_completed_at),
        'completed_at': _isoformat(artifact.completed_at),
        'duration_seconds': _duration_seconds(artifact.started_at, artifact.completed_at),
        'error_message': artifact.error_message,
        'failure_summary': _friendly_error_summary(artifact.error_message),
    }


def _duration_seconds(
    started_at,
    completed_at,
) -> int | None:
    if started_at is None or completed_at is None:
        return None
    start_value = started_at if started_at.tzinfo is not None else started_at.replace(tzinfo=UTC)
    end_value = completed_at if completed_at.tzinfo is not None else completed_at.replace(tzinfo=UTC)
    return max(int((end_value - start_value).total_seconds()), 0)


def _friendly_error_summary(message: str | None) -> str:
    normalized = str(message or '').strip()
    if not normalized:
        return 'The lifecycle failed and requires operator review.'
    lowered = normalized.lower()
    if 'checksum' in lowered:
        return 'Stored archive verification failed.'
    if 'size verification failed' in lowered or 'size mismatch' in lowered:
        return 'Stored archive size did not match the registry record.'
    if 'connection' in lowered or 'timeout' in lowered or 'refused' in lowered:
        return 'KAORI could not reach a required service during the lifecycle job.'
    if 'permission' in lowered or 'access denied' in lowered or 'forbidden' in lowered:
        return 'The lifecycle job was blocked by an authorization or permission failure.'
    if 'archive selection changed' in lowered:
        return 'The eligible record set changed while the archive was being generated.'
    if 'record_id' in lowered:
        return 'Archive cleanup could not map archived records back to source IDs.'
    if ':' in normalized:
        left, right = normalized.split(':', 1)
        if left and right.strip():
            return right.strip().rstrip('.') + '.'
    normalized = normalized.rstrip('.')
    return f'{normalized}.' if normalized else 'The lifecycle failed and requires operator review.'


def _isoformat(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
