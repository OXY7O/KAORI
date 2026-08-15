from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from flask import current_app

from app.extensions.db import db
from app.jobs.dispatcher import enqueue_canonical_job
from app.jobs.execution import JobCancellationRequested, JobExecutionContext
from app.models.user import User
from app.notifications.service import (
    create_notification,
)
from app.retention.domains import get_archive_domain
from app.retention.policy_service import get_or_create_policy, scheduled_domains
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
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    execution = JobExecutionContext(self.request.id) if job_execution_id is not None else None
    try:
        if execution is not None:
            execution.start(
                message=f'Building {domain_name} archive boundary.',
                total=4,
                percent=5,
                stage='Preparing Retention Boundary',
                target=domain_name.replace('_', ' ').title(),
            )
            execution.checkpoint(
                current=1,
                total=4,
                percent=25,
                stage='Writing Archive',
                target=domain_name.replace('_', ' ').title(),
                message='Writing archive data and manifest.',
            )
        result = run_retention_archive(
            domain_name=domain_name,
            trigger_type=trigger_type,
            cleanup=cleanup,
            triggered_by_user_id=requested_by_user_id,
            celery_task_id=self.request.id,
        )
        policy = get_archive_domain(domain_name).build_policy()
        result['archive_purge'] = purge_expired_archives(
            domain_name=domain_name,
            retention_days=policy.archive_retention_days,
            dry_run=False,
        )
        if execution is not None:
            execution.checkpoint(
                current=3,
                total=4,
                percent=90,
                stage='Finalizing Retention Result',
                target=domain_name.replace('_', ' ').title(),
                message='Archive verified; finalizing lifecycle result.',
            )
            execution.succeed(
                result_summary=result,
                result_type='archive_artifact',
                result_reference=str(result.get('archive_id') or ''),
            )
        _notify_requester(
            user_id=requested_by_user_id,
            result=result,
            cleanup=cleanup,
        )
        return result
    except JobCancellationRequested as exc:
        db.session.rollback()
        if execution is not None:
            execution.canceled(message=str(exc))
        return {
            'domain': domain_name,
            'status': 'canceled',
            'cleanup_requested': cleanup,
        }
    except Exception as exc:
        db.session.rollback()
        retry_number = int(getattr(self.request, 'retries', 0) or 0)
        if retry_number < 1 and _is_retryable_retention_error(exc):
            retry_delay = max(int(current_app.config.get('RETENTION_RETRY_DELAY_SECONDS', 60) or 60), 1)
            logger.warning(
                'Transient retention failure for %s; retrying once in %s seconds.',
                domain_name,
                retry_delay,
                exc_info=True,
            )
            if execution is not None:
                execution.retrying(
                    message=f'Transient failure; retrying attempt {retry_number + 2} of 2',
                    error=exc,
                )
            raise self.retry(exc=exc, countdown=retry_delay, max_retries=1)

        logger.exception('Retention task failed for %s.', domain_name)
        if execution is not None:
            execution.fail(exc, error_code='data_lifecycle_failed')
        _notify_failure(
            user_id=requested_by_user_id,
            domain_name=domain_name,
            cleanup=cleanup,
            trigger_type=trigger_type,
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
        ('operational_activity', 'job_execution', 'runtime_observation', 'analytics_snapshot', 'generated_report'),
    )
    if isinstance(configured_domains, str):
        configured_domains = tuple(
            item.strip().lower().replace('-', '_') for item in configured_domains.split(',') if item.strip()
        )

    configured_domains = list(configured_domains)
    for domain_name in configured_domains:
        domain = get_archive_domain(domain_name)
        get_or_create_policy(domain_name, domain.build_policy())
    configured_domains = scheduled_domains(configured_domains)

    results: dict[str, Any] = {}
    for domain_name in configured_domains:
        try:
            domain = get_archive_domain(domain_name)
            policy = domain.build_policy()
            if not policy.enabled:
                results[domain_name] = {'status': 'disabled'}
                continue
            stored_policy = get_or_create_policy(domain_name, policy)
            cleanup = stored_policy.operation_mode == 'archive_and_cleanup'
            operation = stored_policy.operation_mode
            job, created = enqueue_canonical_job(
                task=run_domain_retention_task,
                task_kwargs={
                    'domain_name': domain_name,
                    'cleanup': cleanup,
                    'trigger_type': 'scheduled',
                    'requested_by_user_id': None,
                },
                job_type='data_lifecycle',
                operation=operation,
                queue_name=str(current_app.config.get('RETENTION_CELERY_QUEUE', 'maintenance')),
                workload_class='maintenance',
                requested_by_user_id=None,
                resource_group=f'data-lifecycle:{domain_name}',
                scope_type='data_domain',
                scope_key=domain_name,
                parameters={
                    'domain': domain_name,
                    'mode': operation,
                    'retention_days': policy.retention_days,
                },
                payload={'trigger_type': 'scheduled'},
                max_attempts=2,
            )
            results[domain_name] = {
                'status': 'queued' if created else 'already_active',
                'job_execution_id': job.id,
                'task_id': job.celery_task_id,
            }
        except Exception as exc:
            db.session.rollback()
            logger.exception('Scheduled retention dispatch failed for %s.', domain_name)
            _notify_failure(
                user_id=None,
                domain_name=domain_name,
                cleanup=True,
                trigger_type='scheduled',
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

    domain_name = str(result.get('domain') or 'data')
    domain_label = _domain_label(domain_name)
    if result.get('status') == 'no_data':
        title = f'{domain_label} retention found no eligible records'
        message = f'No {domain_label.lower()} records were old enough to archive.'
        status = 'info'
    else:
        record_count = int(result.get('record_count') or 0)
        deleted_count = int(result.get('cleanup_deleted_count') or 0)
        title = f'{domain_label} archive and cleanup completed' if cleanup else f'{domain_label} archive completed'
        message = (
            f'{record_count} records were archived and {deleted_count} were removed from hot storage.'
            if cleanup
            else f'{record_count} records were archived without database cleanup.'
        )
        status = 'warning' if result.get('status') == 'cleanup_partial' else 'success'

    _safe_create_notification(
        user_id=user_id,
        status=status,
        title=title,
        message=message,
        detail='Review Platform Operations → Data Lifecycle for archive status, checksum, and download actions.',
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
    trigger_type: str,
    error: Exception,
) -> None:
    activity_owner_user_id = _resolve_activity_owner_user_id(user_id)
    if activity_owner_user_id is None:
        return

    actor_metadata: dict[str, Any] = {}
    if trigger_type == 'scheduled' and user_id is None:
        actor_metadata = {
            'actor_display_name': 'System scheduler',
            'actor_role': 'Background worker',
            'actor_email': 'Automatic schedule',
            'auth_source': 'system',
        }

    _safe_create_notification(
        user_id=activity_owner_user_id,
        status='error',
        title=f'{_domain_label(domain_name)} retention failed',
        message='The archive-first retention job stopped before it could complete safely.',
        detail='Database cleanup remains blocked. Review Platform Operations → Data Lifecycle and Activity Audit Log before retrying.',
        metadata={
            'domain': domain_name,
            'cleanup_requested': cleanup,
            'trigger_type': trigger_type,
            'error_type': type(error).__name__,
            'reason': _retention_error_summary(error),
            'error_message': f'{type(error).__name__}: {error}',
            **actor_metadata,
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
            event_type='data_lifecycle_retention',
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url='/platform-operations/data-lifecycle/?tab=history',
            metadata=metadata,
        )
    except Exception:
        db.session.rollback()
        logger.exception('Could not create the retention completion notification.')


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


def _is_retryable_retention_error(error: Exception) -> bool:
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    normalized = f'{type(error).__name__}: {error}'.strip().lower()
    return any(
        marker in normalized
        for marker in (
            'endpointconnectionerror',
            'could not connect to the endpoint',
            'connection refused',
            'connection reset',
            'connection timed out',
            'read timeout',
            'connect timeout',
            'temporarily unavailable',
            'service unavailable',
            'gaierror',
            'name or service not known',
        )
    )


def _retention_error_summary(error: Exception) -> str:
    normalized = str(error).strip()
    lowered = normalized.lower()
    if (
        'endpointconnectionerror' in lowered
        or 'could not connect to the endpoint' in lowered
        or 'connection refused' in lowered
        or 'connection timed out' in lowered
        or 'gaierror' in lowered
        or 'name or service not known' in lowered
    ):
        return 'Archive storage could not be reached.'
    if 'checksum' in lowered:
        return 'Archive verification failed.'
    if 'access denied' in lowered or 'forbidden' in lowered or 'permission' in lowered:
        return 'Archive storage access was denied.'
    if 'size verification failed' in lowered or 'size mismatch' in lowered:
        return 'Archive size verification failed.'
    return 'Archive lifecycle failed and requires operator review.'


def _domain_label(domain_name: str) -> str:
    return {
        'operational_activity': 'Activity Audit',
        'job_execution': 'Job Execution',
        'generated_report': 'Generated Reports',
    }.get(domain_name, domain_name.replace('_', ' ').title())
