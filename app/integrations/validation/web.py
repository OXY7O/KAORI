from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from flask import current_app

from app.integrations.validation.state import (
    build_validation_snapshot,
    claim_validation_job,
    get_active_validation_task_id,
    release_validation_job,
)
from app.integrations.validation.tasks import (
    validate_integration_binding,
    validate_integration_instance,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _queue_name() -> str:
    return (
        str(current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE') or 'integration-validation').strip()
        or 'integration-validation'
    )


def enqueue_instance_validation(
    *,
    provider_type: str,
    instance_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    operation = 'full_validation'
    active_task_id = get_active_validation_task_id(
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
    )
    if active_task_id:
        return build_validation_snapshot(active_task_id), False
    if operation == 'full_validation':
        runtime_task_id = get_active_validation_task_id(
            provider_type=provider_type,
            operation='runtime_refresh',
            instance_id=instance_id,
        )
        if runtime_task_id:
            return build_validation_snapshot(runtime_task_id), False

    task_id = str(uuid4())
    created_at = _now_iso()
    metadata = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': operation,
        'instance_id': instance_id,
        'binding_id': None,
        'requested_by_user_id': requested_by_user_id,
        'created_at': created_at,
        'status': 'info',
        'title': 'Validation queued',
        'message': 'KAORI queued the validation job for the dedicated worker.',
        'detail': 'This page will refresh the validation workspace when the worker completes.',
    }
    acquired = claim_validation_job(
        task_id=task_id,
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=None,
        metadata=metadata,
        conflicting_operations=('runtime_refresh',) if operation == 'full_validation' else (),
    )
    if not acquired:
        active_task_id = get_active_validation_task_id(
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
        )
        if active_task_id:
            return build_validation_snapshot(active_task_id), False
        raise RuntimeError('Could not acquire the integration validation lock.')
    try:
        validate_integration_instance.apply_async(
            kwargs={
                'provider_type': provider_type,
                'instance_id': instance_id,
                'requested_by_user_id': requested_by_user_id,
                'trigger_type': 'manual',
            },
            task_id=task_id,
            queue=_queue_name(),
        )
    except Exception:
        release_validation_job(
            task_id=task_id,
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
        )
        raise
    return build_validation_snapshot(task_id), True


def enqueue_binding_validation(
    *,
    provider_type: str,
    instance_id: int,
    binding_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    operation = 'binding_validation'
    active_task_id = get_active_validation_task_id(
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
    )
    if active_task_id:
        return build_validation_snapshot(active_task_id), False

    task_id = str(uuid4())
    created_at = _now_iso()
    metadata = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': operation,
        'instance_id': instance_id,
        'binding_id': binding_id,
        'requested_by_user_id': requested_by_user_id,
        'created_at': created_at,
        'status': 'info',
        'title': 'Binding validation queued',
        'message': 'KAORI queued the scope selector validation.',
        'detail': 'Source resolution remains blocked until the worker completes.',
    }
    acquired = claim_validation_job(
        task_id=task_id,
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
        metadata=metadata,
    )
    if not acquired:
        active_task_id = get_active_validation_task_id(
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
            binding_id=binding_id,
        )
        if active_task_id:
            return build_validation_snapshot(active_task_id), False
        raise RuntimeError('Could not acquire the binding validation lock.')
    try:
        validate_integration_binding.apply_async(
            kwargs={
                'provider_type': provider_type,
                'instance_id': instance_id,
                'binding_id': binding_id,
                'requested_by_user_id': requested_by_user_id,
            },
            task_id=task_id,
            queue=_queue_name(),
        )
    except Exception:
        release_validation_job(
            task_id=task_id,
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
            binding_id=binding_id,
        )
        raise
    return build_validation_snapshot(task_id), True


def validate_snapshot_access(
    snapshot: dict[str, Any],
    *,
    provider_type: str,
    instance_id: int,
    binding_id: int | None = None,
) -> bool:
    """Validate that a task belongs to the provider workspace being rendered.

    Validation jobs are instance-scoped, not browser-session-scoped. Any operator
    with the route permission may observe an already-running job for the same
    provider target. Completion toast feedback remains limited to the operator
    who originally queued the task.
    """
    return (
        str(snapshot.get('provider_type') or '') == provider_type
        and int(snapshot.get('instance_id') or 0) == int(instance_id)
        and (
            binding_id is None
            or int(snapshot.get('binding_id') or 0) == int(binding_id)
        )
    )


def snapshot_feedback_for_user(
    snapshot: dict[str, Any],
    *,
    user_id: int,
) -> dict[str, Any] | None:
    if not snapshot.get('is_complete'):
        return None
    if int(snapshot.get('requested_by_user_id') or 0) != int(user_id):
        return None
    feedback = snapshot.get('feedback')
    return feedback if isinstance(feedback, dict) else None


def enqueue_runtime_health_refresh(
    *,
    provider_type: str,
    instance_id: int,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    from app.integrations.validation.tasks import refresh_integration_runtime_instance

    operation = 'runtime_refresh'
    active_task_id = get_active_validation_task_id(
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
    )
    if active_task_id:
        return build_validation_snapshot(active_task_id), False
    full_validation_task_id = get_active_validation_task_id(
        provider_type=provider_type,
        operation='full_validation',
        instance_id=instance_id,
    )
    if full_validation_task_id:
        return build_validation_snapshot(full_validation_task_id), False

    task_id = str(uuid4())
    created_at = _now_iso()
    metadata = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': operation,
        'instance_id': instance_id,
        'binding_id': None,
        'requested_by_user_id': requested_by_user_id,
        'created_at': created_at,
        'status': 'info',
        'title': 'Runtime health refresh queued',
        'message': 'KAORI queued the lightweight runtime health refresh.',
        'detail': 'Full capability evidence will be preserved while the worker checks reachability and response health.',
    }
    if not claim_validation_job(
        task_id=task_id,
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=None,
        metadata=metadata,
        conflicting_operations=('full_validation',),
    ):
        active_task_id = get_active_validation_task_id(
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
        )
        if active_task_id:
            return build_validation_snapshot(active_task_id), False
        raise RuntimeError('Could not acquire the runtime refresh lock.')
    try:
        refresh_integration_runtime_instance.apply_async(
            kwargs={
                'provider_type': provider_type,
                'instance_id': instance_id,
                'requested_by_user_id': requested_by_user_id,
                'trigger_type': 'manual',
            },
            task_id=task_id,
            queue=_queue_name(),
        )
    except Exception:
        release_validation_job(
            task_id=task_id,
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
        )
        raise
    return build_validation_snapshot(task_id), True
