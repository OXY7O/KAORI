from __future__ import annotations

from typing import Any, cast

from celery import Task
from flask import current_app

from app.models.job import JobExecution
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.service import create_or_attach_job, mark_job_failed


class JobWorkerUnavailable(RuntimeError):
    """Raised when no live worker can safely accept a registered job task."""


def ensure_task_registered_for_queue(*, task: object, queue_name: str) -> None:
    """Require one live queue consumer to advertise the task before dispatch.

    Celery accepts a message even when the target worker was started before a
    newly-added task existed. The worker then discards the unknown task while
    KAORI would otherwise keep the canonical execution in ``queued`` forever.
    Heavy materialization jobs opt into this runtime preflight so that a stale
    worker is rejected before a JobExecution slot is created.
    """
    celery_app = current_app.extensions.get('celery')
    if celery_app is None:
        raise JobWorkerUnavailable('Celery is not initialized for job dispatch.')

    task_name = str(getattr(task, 'name', '') or '')
    if not task_name:
        raise JobWorkerUnavailable('The registered job task does not expose a Celery task name.')

    try:
        inspector = celery_app.control.inspect(timeout=1.25)
        active_queues = inspector.active_queues() or {}
    except Exception as exc:
        raise JobWorkerUnavailable(
            f'Celery worker inspection failed with {type(exc).__name__}; '
            f'KAORI cannot safely dispatch to {queue_name!r}.'
        ) from exc

    queue_workers = {
        worker
        for worker, queues in active_queues.items()
        if any(str(queue.get('name') or '') == queue_name for queue in (queues or []))
    }
    if not queue_workers:
        raise JobWorkerUnavailable(
            f'No live Celery worker is consuming the {queue_name!r} queue. Restart the target worker before retrying.'
        )

    try:
        registry_inspector = celery_app.control.inspect(
            destination=sorted(queue_workers),
            timeout=1.75,
        )
        registered = registry_inspector.registered() or {}
    except Exception as exc:
        raise JobWorkerUnavailable(
            f'Workers consume {queue_name!r}, but task-registry inspection failed with {type(exc).__name__}. '
            'Retry after worker remote control is available.'
        ) from exc

    task_workers = {
        worker
        for worker in queue_workers
        if task_name in {str(name) for name in (registered.get(worker) or [])}
    }
    if task_workers:
        return

    responders = queue_workers.intersection(registered)
    if not responders:
        raise JobWorkerUnavailable(
            f'Workers consume {queue_name!r}, but none returned a task registry. '
            'KAORI did not dispatch because worker task ownership could not be verified.'
        )

    responder_list = ', '.join(sorted(responders))
    raise JobWorkerUnavailable(
        f'Workers consuming {queue_name!r} do not advertise task {task_name!r} ({responder_list}). '
        'Restart the target worker so its task registry matches the deployed KAORI source.'
    )


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
    integration_type: str | None = None,
    integration_instance_id: int | None = None,
    scope_type: str | None = None,
    scope_key: str | None = None,
    max_attempts: int = 3,
    priority: int | None = None,
    soft_time_limit_seconds: int | None = None,
    hard_time_limit_seconds: int | None = None,
    require_registered_worker: bool = False,
) -> tuple[JobExecution, bool]:
    """Create or attach to one idempotent job and dispatch it exactly once.

    This provider-neutral dispatcher is the required entry point for future
    analytics and forecasting jobs. Integration validation retains its additional
    provider lock because it has cross-operation conflict rules.
    """
    if require_registered_worker:
        ensure_task_registered_for_queue(task=task, queue_name=queue_name)

    job, created = create_or_attach_job(
        job_type=job_type,
        operation=operation,
        queue_name=queue_name,
        workload_class=workload_class,
        requested_by_user_id=requested_by_user_id,
        integration_type=integration_type,
        integration_instance_id=integration_instance_id,
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
    from app.platform_operations.jobs.registry import get_job_definition

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
