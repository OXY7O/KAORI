from __future__ import annotations

from typing import Any, cast

from celery import Task

from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.service import create_or_attach_job, mark_job_failed
from app.models.job import JobExecution


def enqueue_canonical_job(
    *,
    task: object,
    task_kwargs: dict[str, Any],
    job_type: str,
    operation: str,
    queue_name: str,
    workload_class: str,
    requested_by_user_id: int | None,
    resource_group: str | None,
    parameters: dict[str, Any],
    payload: dict[str, Any] | None = None,
    provider_type: str | None = None,
    provider_instance_id: int | None = None,
    scope_type: str | None = None,
    scope_key: str | None = None,
    max_attempts: int = 3,
    priority: int | None = None,
    soft_time_limit_seconds: int | None = None,
    hard_time_limit_seconds: int | None = None,
) -> tuple[JobExecution, bool]:
    """Create or attach to one idempotent job and dispatch it exactly once.

    This provider-neutral dispatcher is the required entry point for future
    analytics and forecasting jobs. Integration validation retains its additional
    provider lock because it has cross-operation conflict rules.
    """
    job, created = create_or_attach_job(
        job_type=job_type,
        operation=operation,
        queue_name=queue_name,
        workload_class=workload_class,
        requested_by_user_id=requested_by_user_id,
        provider_type=provider_type,
        provider_instance_id=provider_instance_id,
        scope_type=scope_type,
        scope_key=scope_key,
        resource_group=resource_group,
        parameters=parameters,
        payload=payload,
        max_attempts=max_attempts,
        priority=priority,
    )
    if not created:
        return job, False
    if not job.celery_task_id:
        raise RuntimeError('Canonical job does not have a Celery task identifier.')
    try:
        apply_options: dict[str, Any] = {
            'kwargs': {**task_kwargs, 'job_execution_id': job.id},
            'task_id': job.celery_task_id,
            'queue': queue_name,
            'priority': job.priority,
        }
        if soft_time_limit_seconds is not None:
            apply_options['soft_time_limit'] = max(int(soft_time_limit_seconds), 1)
        if hard_time_limit_seconds is not None:
            apply_options['time_limit'] = max(int(hard_time_limit_seconds), 1)
        cast(Task, task).apply_async(**apply_options)
    except Exception as exc:
        mark_job_failed(job.celery_task_id, error=exc, error_code='dispatch_failed')
        raise
    return job, True


def dispatch_registered_job(
    *,
    job_key: str,
    trigger_type: str,
    requested_by_user_id: int | None,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    """Resolve one static job definition and dispatch it through its domain adapter."""
    from app.jobs.registry import get_job_definition

    definition = get_job_definition(job_key)
    if trigger_type == 'manual' and not definition.manual_execution_supported:
        raise ValueError(f'{definition.name} does not support manual execution.')
    if trigger_type == 'scheduled' and not definition.schedule_supported:
        raise ValueError(f'{definition.name} does not support scheduled execution.')
    if trigger_type not in {'manual', 'scheduled', 'on_demand'}:
        raise ValueError(f'Unsupported job trigger type: {trigger_type}')
    return definition.dispatch(
        requested_by_user_id=requested_by_user_id,
        trigger_type=trigger_type,
        parameters=parameters,
    )
