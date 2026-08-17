from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from flask import current_app

from app.integrations.contracts import IntegrationInstanceNotFound, IntegrationNotRegistered
from app.integrations.registry import get_integration
from app.integrations.validation.state import (
    build_validation_snapshot,
    claim_validation_job,
    get_active_validation_task_id,
    release_validation_job,
)
from app.integrations.validation.tasks import (
    refresh_integration_runtime_instance,
    validate_integration_binding,
    validate_integration_instance,
)
from app.models.job import JobExecutionSubscriber
from app.platform_operations.jobs.constants import WORKLOAD_RUNTIME, WORKLOAD_VALIDATION
from app.platform_operations.jobs.fingerprint import build_deduplication_key
from app.platform_operations.jobs.service import (
    acquire_resource_admission_locks,
    create_or_attach_job,
    find_active_job,
    mark_job_failed,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _validation_queue_name() -> str:
    return (
        str(current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE') or 'integration-validation').strip()
        or 'integration-validation'
    )


def _runtime_queue_name() -> str:
    return (
        str(current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE') or 'integration-runtime').strip()
        or 'integration-runtime'
    )


def _dedup_key(
    *, integration_type: str, operation: str, integration_instance_id: int, binding_id: int | None = None
) -> str:
    return build_deduplication_key(
        'integration',
        integration_type,
        integration_instance_id,
        operation,
        binding_id,
    )


def _metadata(
    *,
    task_id: str,
    job_execution_id: int,
    integration_type: str,
    operation: str,
    integration_instance_id: int,
    binding_id: int | None,
    requested_by_user_id: int | None,
    title: str,
    message: str,
    detail: str,
) -> dict[str, Any]:
    return {
        'task_id': task_id,
        'job_execution_id': job_execution_id,
        'integration_type': integration_type,
        'operation': operation,
        'integration_instance_id': integration_instance_id,
        'binding_id': binding_id,
        'requested_by_user_id': requested_by_user_id,
        'created_at': _now_iso(),
        'status': 'info',
        'title': title,
        'message': message,
        'detail': detail,
    }


def _assert_provider_target_exists(*, integration_type: str, integration_instance_id: int) -> None:
    try:
        get_integration(integration_type).require_record_for_canonical(integration_instance_id)
    except IntegrationNotRegistered as exc:
        raise ValueError(f'Unsupported integration type: {integration_type}.') from exc
    except IntegrationInstanceNotFound as exc:
        raise RuntimeError('The integration connection was deleted before KAORI could admit the job.') from exc


def _enqueue_job(
    *,
    integration_type: str,
    operation: str,
    integration_instance_id: int,
    binding_id: int | None,
    requested_by_user_id: int,
    queue_name: str,
    workload_class: str,
    task: Callable[..., Any],
    task_kwargs: dict[str, Any],
    title: str,
    message: str,
    detail: str,
    conflicting_operation: str | None = None,
) -> tuple[dict[str, Any], bool]:
    if conflicting_operation:
        conflict = find_active_job(
            integration_type=integration_type,
            integration_instance_id=integration_instance_id,
            operation=conflicting_operation,
        )
        if conflict is not None and conflict.celery_task_id:
            return build_validation_snapshot(conflict.celery_task_id), False

    deduplication_key = _dedup_key(
        integration_type=integration_type,
        operation=operation,
        integration_instance_id=integration_instance_id,
        binding_id=binding_id,
    )
    scope_key = f'binding:{binding_id}' if binding_id is not None else None
    resource_group = f'integration:{integration_type}:{integration_instance_id}'
    acquire_resource_admission_locks(resource_group)
    _assert_provider_target_exists(integration_type=integration_type, integration_instance_id=integration_instance_id)
    job, created = create_or_attach_job(
        job_type='integration_operation',
        operation=operation,
        queue_name=queue_name,
        workload_class=workload_class,
        requested_by_user_id=requested_by_user_id,
        integration_type=integration_type,
        integration_instance_id=integration_instance_id,
        scope_type='integration_binding' if binding_id is not None else 'integration_instance',
        scope_key=scope_key,
        resource_group=resource_group,
        parameters={
            'integration_type': integration_type,
            'integration_instance_id': integration_instance_id,
            'binding_id': binding_id,
            'operation': operation,
        },
        payload={
            'integration_type': integration_type,
            'integration_instance_id': integration_instance_id,
            'binding_id': binding_id,
            'trigger_type': 'manual',
        },
        deduplication_key=deduplication_key,
        max_attempts=3,
    )
    if not job.celery_task_id:
        raise RuntimeError('Canonical job record does not have a Celery task identifier.')
    if not created:
        return build_validation_snapshot(job.celery_task_id), False

    metadata = _metadata(
        task_id=job.celery_task_id,
        job_execution_id=job.id,
        integration_type=integration_type,
        operation=operation,
        integration_instance_id=integration_instance_id,
        binding_id=binding_id,
        requested_by_user_id=requested_by_user_id,
        title=title,
        message=message,
        detail=detail,
    )
    acquired = claim_validation_job(
        task_id=job.celery_task_id,
        integration_type=integration_type,
        operation=operation,
        integration_instance_id=integration_instance_id,
        binding_id=binding_id,
        metadata=metadata,
        conflicting_operations=(conflicting_operation,) if conflicting_operation else (),
    )
    if not acquired:
        mark_job_failed(
            job.celery_task_id,
            error='Could not acquire the provider resource lock.',
            error_code='resource_lock_conflict',
        )
        active_task_id = get_active_validation_task_id(
            integration_type=integration_type,
            operation=operation,
            integration_instance_id=integration_instance_id,
            binding_id=binding_id,
        )
        if active_task_id:
            return build_validation_snapshot(active_task_id), False
        raise RuntimeError('Could not acquire the integration job lock.')
    try:
        task.apply_async(
            kwargs={
                **task_kwargs,
                'job_execution_id': job.id,
            },
            task_id=job.celery_task_id,
            queue=queue_name,
            priority=job.priority,
        )
    except Exception as exc:
        release_validation_job(
            task_id=job.celery_task_id,
            integration_type=integration_type,
            operation=operation,
            integration_instance_id=integration_instance_id,
            binding_id=binding_id,
        )
        mark_job_failed(job.celery_task_id, error=exc, error_code='dispatch_failed')
        raise
    return build_validation_snapshot(job.celery_task_id), True


def enqueue_instance_validation(
    *,
    integration_type: str,
    integration_instance_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    return _enqueue_job(
        integration_type=integration_type,
        operation='full_validation',
        integration_instance_id=integration_instance_id,
        binding_id=None,
        requested_by_user_id=requested_by_user_id,
        queue_name=_validation_queue_name(),
        workload_class=WORKLOAD_VALIDATION,
        task=validate_integration_instance,
        task_kwargs={
            'integration_type': integration_type,
            'integration_instance_id': integration_instance_id,
            'requested_by_user_id': requested_by_user_id,
            'trigger_type': 'manual',
        },
        title='Validation queued',
        message='KAORI queued the validation job for the dedicated worker.',
        detail='This page will refresh the validation workspace when the worker completes.',
        conflicting_operation='runtime_refresh',
    )


def enqueue_binding_validation(
    *,
    integration_type: str,
    integration_instance_id: int,
    binding_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    return _enqueue_job(
        integration_type=integration_type,
        operation='binding_validation',
        integration_instance_id=integration_instance_id,
        binding_id=binding_id,
        requested_by_user_id=requested_by_user_id,
        queue_name=_validation_queue_name(),
        workload_class=WORKLOAD_VALIDATION,
        task=validate_integration_binding,
        task_kwargs={
            'integration_type': integration_type,
            'integration_instance_id': integration_instance_id,
            'binding_id': binding_id,
            'requested_by_user_id': requested_by_user_id,
        },
        title='Binding validation queued',
        message='KAORI queued the scope selector validation.',
        detail='Source resolution remains blocked until the worker completes.',
    )


def validate_snapshot_access(
    snapshot: dict[str, Any],
    *,
    integration_type: str,
    integration_instance_id: int,
    binding_id: int | None = None,
) -> bool:
    return (
        str(snapshot.get('integration_type') or '') == integration_type
        and int(snapshot.get('integration_instance_id') or 0) == int(integration_instance_id)
        and (binding_id is None or int(snapshot.get('binding_id') or 0) == int(binding_id))
    )


def snapshot_feedback_for_user(
    snapshot: dict[str, Any],
    *,
    user_id: int,
) -> dict[str, Any] | None:
    if not snapshot.get('is_complete'):
        return None
    job_execution_id = int(snapshot.get('job_execution_id') or 0)
    if job_execution_id:
        subscribed = JobExecutionSubscriber.query.filter_by(
            job_execution_id=job_execution_id,
            user_id=user_id,
        ).first()
        if subscribed is None:
            return None
    elif int(snapshot.get('requested_by_user_id') or 0) != int(user_id):
        return None
    feedback = snapshot.get('feedback')
    return feedback if isinstance(feedback, dict) else None


def enqueue_runtime_health_refresh(
    *,
    integration_type: str,
    integration_instance_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    return _enqueue_job(
        integration_type=integration_type,
        operation='runtime_refresh',
        integration_instance_id=integration_instance_id,
        binding_id=None,
        requested_by_user_id=requested_by_user_id,
        queue_name=_runtime_queue_name(),
        workload_class=WORKLOAD_RUNTIME,
        task=refresh_integration_runtime_instance,
        task_kwargs={
            'integration_type': integration_type,
            'integration_instance_id': integration_instance_id,
            'requested_by_user_id': requested_by_user_id,
            'trigger_type': 'manual',
        },
        title='Runtime health refresh queued',
        message='KAORI queued the lightweight runtime health refresh.',
        detail='Full capability evidence will be preserved while the worker checks reachability and response health.',
        conflicting_operation='full_validation',
    )
