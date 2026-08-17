from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app, url_for

from app.extensions.db import db
from app.platform_operations.data_lifecycle.retention.domains import get_archive_domain
from app.platform_operations.data_lifecycle.retention.policy_service import get_policy, update_policy
from app.platform_operations.data_lifecycle.retention.service import get_archive_download_path, verify_archive_artifact
from app.platform_operations.data_lifecycle.retention.tasks import run_domain_retention_task
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job
from app.platform_operations.notifications.service import record_operational_activity


def _int_value(values: Mapping[str, Any], name: str, default: int) -> int:
    try:
        return int(values.get(name, default))
    except (TypeError, ValueError):
        return default


def update_lifecycle_policy(*, domain_name: str, values: Mapping[str, Any], user_id: int) -> dict[str, Any]:
    domain = get_archive_domain(domain_name)
    fallback = domain.build_policy()
    try:
        settings = dict(fallback.settings or {})
        batch_size = _int_value(values, 'batch_size', fallback.batch_size)
        if domain_name == 'job_execution':
            settings['workload_retention_days'] = {
                'runtime': max(_int_value(values, 'runtime_retention_days', 30), 1),
                'validation': max(_int_value(values, 'validation_retention_days', 30), 1),
                'analytics': max(_int_value(values, 'analytics_retention_days', 90), 1),
                'forecasting': max(_int_value(values, 'forecasting_retention_days', 180), 1),
                'standard': max(_int_value(values, 'hot_retention_days', 90), 1),
            }
            settings['failed_retention_days'] = max(_int_value(values, 'failed_retention_days', 90), 1)
            settings['preserve_result_references'] = True
        elif domain_name == 'generated_report':
            hot_days = max(_int_value(values, 'hot_retention_days', fallback.retention_days), 1)
            settings['failed_retention_days'] = max(_int_value(values, 'failed_retention_days', 30), 1)
            settings['archived_retention_days'] = max(
                _int_value(values, 'archived_retention_days', max(hot_days, 180)),
                hot_days,
            )
            settings['archive_binary_artifacts'] = True
            settings['protect_active_generation'] = True
            batch_size = max(100, min(batch_size, 2500))

        update_policy(
            domain=domain_name,
            fallback=fallback,
            enabled=values.get('enabled') == 'on',
            hot_retention_days=_int_value(values, 'hot_retention_days', fallback.retention_days),
            archive_retention_days=_int_value(values, 'archive_retention_days', fallback.archive_retention_days),
            batch_size=batch_size,
            operation_mode=str(values.get('operation_mode') or 'archive_and_cleanup'),
            schedule_enabled=values.get('schedule_enabled') == 'on',
            schedule_hour=_int_value(values, 'schedule_hour', 2),
            schedule_minute=_int_value(values, 'schedule_minute', 0),
            protect_unreviewed=values.get('protect_unreviewed') == 'on',
            protected_max_days=(
                _int_value(values, 'protected_max_days', fallback.protected_max_days or fallback.retention_days)
                if domain_name == 'operational_activity'
                else None
            ),
            settings=settings,
        )
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_policy_updated',
            status='success',
            title='Data lifecycle policy updated',
            message=f'{domain_name.replace("_", " ").title()} now uses the updated retention and archive policy.',
            detail='The new boundary is applied by future previews and lifecycle jobs.',
            action_url=url_for('platform_operations.data_lifecycle.index', domain=domain_name),
            action_label='Open Data Lifecycle',
            action_icon='archive-restore',
            metadata={'domain': domain_name},
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not update data lifecycle policy.')
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_policy_update_failed',
            status='error',
            title='Data lifecycle policy update failed',
            message=f'The policy was not changed because of {type(exc).__name__}.',
            detail='Review the submitted retention values and application logs before retrying.',
            action_url=url_for('platform_operations.data_lifecycle.index', domain=domain_name),
            metadata={'domain': domain_name, 'error_type': type(exc).__name__},
        )


def queue_lifecycle_execution(*, domain_name: str, mode: str, user_id: int) -> dict[str, Any]:
    normalized_mode = str(mode or '').strip().lower()
    if normalized_mode not in {'archive_only', 'archive_and_cleanup'}:
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_execution_rejected',
            status='error',
            title='Data lifecycle execution was not queued',
            message='The requested lifecycle mode is not supported.',
            detail='Choose Archive Only or Archive & Cleanup. No archive was created and no hot record was removed.',
            action_url=url_for('platform_operations.data_lifecycle.index', domain=domain_name),
            metadata={'domain': domain_name, 'mode': normalized_mode or 'missing'},
        )

    cleanup = normalized_mode == 'archive_and_cleanup'
    try:
        domain = get_archive_domain(domain_name)
        stored_policy = get_policy(domain_name)
        policy = domain.build_policy()
        if stored_policy is None or not policy.enabled:
            reason = 'policy_missing' if stored_policy is None else 'policy_disabled'
            title = (
                'Data lifecycle policy is not persisted' if stored_policy is None else 'Data lifecycle policy is paused'
            )
            detail = (
                'Save the policy before execution so KAORI has an authoritative persisted lifecycle contract.'
                if stored_policy is None
                else (
                    'Preview remains available while the policy is paused. Enable and save the policy before execution.'
                )
            )
            return record_operational_activity(
                user_id=user_id,
                event_type='data_lifecycle_execution_rejected',
                status='warning',
                title=title,
                message=(
                    f'{domain_name.replace("_", " ").title()} must have an enabled persisted policy '
                    'before an archive job can be queued.'
                ),
                detail=detail,
                action_url=url_for('platform_operations.data_lifecycle.index', domain=domain_name),
                action_label='Review Data Lifecycle',
                action_icon='archive-restore',
                metadata={'domain': domain_name, 'mode': normalized_mode, 'reason': reason},
            )

        job, created = enqueue_canonical_job(
            task=run_domain_retention_task,
            task_kwargs={
                'domain_name': domain_name,
                'cleanup': cleanup,
                'trigger_type': 'manual',
                'requested_by_user_id': user_id,
            },
            job_type='data_lifecycle',
            operation=normalized_mode,
            queue_name=str(current_app.config.get('RETENTION_CELERY_QUEUE', 'maintenance')),
            workload_class='maintenance',
            requested_by_user_id=user_id,
            resource_group=f'data-lifecycle:{domain_name}',
            scope_type='data_domain',
            scope_key=domain_name,
            parameters={
                'domain': domain_name,
                'mode': normalized_mode,
                'retention_days': policy.retention_days,
                'archive_retention_days': policy.archive_retention_days,
            },
            payload={'trigger_type': 'manual'},
            max_attempts=2,
        )
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_execution_requested',
            status='info',
            title='Data lifecycle execution queued' if created else 'Data lifecycle execution already active',
            message=(
                f'{domain_name.replace("_", " ").title()} archive processing was queued.'
                if created
                else (
                    f'{domain_name.replace("_", " ").title()} already has an active lifecycle job; '
                    'this request was attached to it.'
                )
            ),
            detail='KAORI writes and verifies the archive before cleanup can begin.',
            action_url=url_for('jobs.executions'),
            action_label='Open Jobs & Executions',
            action_icon='list-checks',
            metadata={
                'domain': domain_name,
                'mode': normalized_mode,
                'job_execution_id': job.id,
                'celery_task_id': job.celery_task_id,
                'created': created,
            },
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not queue data lifecycle execution.')
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_execution_queue_failed',
            status='error',
            title='Data lifecycle execution was not queued',
            message=f'The request failed because of {type(exc).__name__}.',
            detail='No archive was created and no hot record was removed.',
            action_url=url_for('platform_operations.data_lifecycle.index', domain=domain_name),
            metadata={'domain': domain_name, 'error_type': type(exc).__name__},
        )


def verify_lifecycle_archive(*, archive_id: str, user_id: int) -> dict[str, Any]:
    try:
        result = verify_archive_artifact(archive_id)
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_archive_verified',
            status='success',
            title='Archive verification completed',
            message='KAORI verified the archive data and manifest checksums.',
            detail='The archive remains available according to its domain archive-retention policy.',
            action_url=url_for('platform_operations.data_lifecycle.index', tab='history'),
            metadata=result,
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not verify lifecycle archive.')
        return record_operational_activity(
            user_id=user_id,
            event_type='data_lifecycle_archive_verification_failed',
            status='error',
            title='Archive verification failed',
            message=f'The archive could not be verified because of {type(exc).__name__}.',
            detail='No hot record was modified.',
            action_url=url_for('platform_operations.data_lifecycle.index', tab='history'),
            metadata={'archive_id': archive_id, 'error_type': type(exc).__name__},
        )


def lifecycle_archive_download(archive_id: str, *, kind: str):
    return get_archive_download_path(archive_id, kind=kind)
