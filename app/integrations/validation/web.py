from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from flask import current_app

from app.extensions import db
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
from app.jobs.constants import WORKLOAD_RUNTIME, WORKLOAD_VALIDATION
from app.jobs.fingerprint import build_deduplication_key
from app.jobs.service import (
    acquire_resource_admission_locks,
    create_or_attach_job,
    find_active_job,
    mark_job_failed,
)
from app.models.alertmanager import AlertmanagerInstance
from app.models.job import JobExecutionSubscriber
from app.models.kubernetes import KubernetesConnection
from app.models.prometheus import PrometheusInstance


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


def _dedup_key(*, provider_type: str, operation: str, instance_id: int, binding_id: int | None = None) -> str:
    return build_deduplication_key(
        'integration',
        provider_type,
        instance_id,
        operation,
        binding_id,
    )


def _metadata(
    *,
    task_id: str,
    job_execution_id: int,
    provider_type: str,
    operation: str,
    instance_id: int,
    binding_id: int | None,
    requested_by_user_id: int | None,
    title: str,
    message: str,
    detail: str,
) -> dict[str, Any]:
    return {
        'task_id': task_id,
        'job_execution_id': job_execution_id,
        'provider_type': provider_type,
        'operation': operation,
        'instance_id': instance_id,
        'binding_id': binding_id,
        'requested_by_user_id': requested_by_user_id,
        'created_at': _now_iso(),
        'status': 'info',
        'title': title,
        'message': message,
        'detail': detail,
    }



def _assert_provider_target_exists(*, provider_type: str, instance_id: int) -> None:
    model_by_provider = {
        'prometheus': PrometheusInstance,
        'alertmanager': AlertmanagerInstance,
        'kubernetes': KubernetesConnection,
    }
    model = model_by_provider.get(provider_type)
    if model is None:
        raise ValueError(f'Unsupported integration provider: {provider_type}.')
    if db.session.get(model, instance_id) is None:
        raise RuntimeError(
            'The integration connection was deleted before KAORI could admit the job.'
        )

def _enqueue_job(
    *,
    provider_type: str,
    operation: str,
    instance_id: int,
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
            provider_type=provider_type,
            provider_instance_id=instance_id,
            operation=conflicting_operation,
        )
        if conflict is not None and conflict.celery_task_id:
            return build_validation_snapshot(conflict.celery_task_id), False

    deduplication_key = _dedup_key(
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
    )
    scope_key = f'binding:{binding_id}' if binding_id is not None else None
    resource_group = f'integration:{provider_type}:{instance_id}'
    acquire_resource_admission_locks(resource_group)
    _assert_provider_target_exists(provider_type=provider_type, instance_id=instance_id)
    job, created = create_or_attach_job(
        job_type='integration_operation',
        operation=operation,
        queue_name=queue_name,
        workload_class=workload_class,
        requested_by_user_id=requested_by_user_id,
        provider_type=provider_type,
        provider_instance_id=instance_id,
        scope_type='integration_binding' if binding_id is not None else 'integration_instance',
        scope_key=scope_key,
        resource_group=resource_group,
        parameters={
            'provider_type': provider_type,
            'instance_id': instance_id,
            'binding_id': binding_id,
            'operation': operation,
        },
        payload={
            'provider_type': provider_type,
            'instance_id': instance_id,
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
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
        requested_by_user_id=requested_by_user_id,
        title=title,
        message=message,
        detail=detail,
    )
    acquired = claim_validation_job(
        task_id=job.celery_task_id,
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
        metadata=metadata,
        conflicting_operations=(conflicting_operation,) if conflicting_operation else (),
    )
    if not acquired:
        mark_job_failed(job.celery_task_id, error='Could not acquire the provider resource lock.', error_code='resource_lock_conflict')
        active_task_id = get_active_validation_task_id(
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
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
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
            binding_id=binding_id,
        )
        mark_job_failed(job.celery_task_id, error=exc, error_code='dispatch_failed')
        raise
    return build_validation_snapshot(job.celery_task_id), True


def enqueue_instance_validation(
    *,
    provider_type: str,
    instance_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    return _enqueue_job(
        provider_type=provider_type,
        operation='full_validation',
        instance_id=instance_id,
        binding_id=None,
        requested_by_user_id=requested_by_user_id,
        queue_name=_validation_queue_name(),
        workload_class=WORKLOAD_VALIDATION,
        task=validate_integration_instance,
        task_kwargs={
            'provider_type': provider_type,
            'instance_id': instance_id,
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
    provider_type: str,
    instance_id: int,
    binding_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    return _enqueue_job(
        provider_type=provider_type,
        operation='binding_validation',
        instance_id=instance_id,
        binding_id=binding_id,
        requested_by_user_id=requested_by_user_id,
        queue_name=_validation_queue_name(),
        workload_class=WORKLOAD_VALIDATION,
        task=validate_integration_binding,
        task_kwargs={
            'provider_type': provider_type,
            'instance_id': instance_id,
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
    provider_type: str,
    instance_id: int,
    binding_id: int | None = None,
) -> bool:
    return (
        str(snapshot.get('provider_type') or '') == provider_type
        and int(snapshot.get('instance_id') or 0) == int(instance_id)
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
    provider_type: str,
    instance_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    return _enqueue_job(
        provider_type=provider_type,
        operation='runtime_refresh',
        instance_id=instance_id,
        binding_id=None,
        requested_by_user_id=requested_by_user_id,
        queue_name=_runtime_queue_name(),
        workload_class=WORKLOAD_RUNTIME,
        task=refresh_integration_runtime_instance,
        task_kwargs={
            'provider_type': provider_type,
            'instance_id': instance_id,
            'requested_by_user_id': requested_by_user_id,
            'trigger_type': 'manual',
        },
        title='Runtime health refresh queued',
        message='KAORI queued the lightweight runtime health refresh.',
        detail='Full capability evidence will be preserved while the worker checks reachability and response health.',
        conflicting_operation='full_validation',
    )
