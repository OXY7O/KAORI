from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from celery import Task
from flask import current_app

from app.integrations.validation.state import (
    claim_validation_job,
    get_active_validation_task_id,
    release_validation_job,
)
from app.integrations.validation.tasks import refresh_integration_runtime_instance
from app.jobs.constants import WORKLOAD_RUNTIME
from app.jobs.fingerprint import build_deduplication_key
from app.jobs.service import create_or_attach_job, mark_job_failed


def _runtime_queue_name() -> str:
    configured = str(current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE') or 'integration-runtime').strip()
    return configured or 'integration-runtime'


def enqueue_runtime_refresh(*, integration_type: str, integration_instance_id: int) -> str | None:
    if get_active_validation_task_id(
        integration_type=integration_type,
        operation='full_validation',
        integration_instance_id=integration_instance_id,
    ):
        return None
    deduplication_key = build_deduplication_key(
        'integration', integration_type, integration_instance_id, 'runtime_refresh'
    )
    job, created = create_or_attach_job(
        job_type='integration_operation',
        operation='runtime_refresh',
        queue_name=_runtime_queue_name(),
        workload_class=WORKLOAD_RUNTIME,
        requested_by_user_id=None,
        integration_type=integration_type,
        integration_instance_id=integration_instance_id,
        scope_type='integration_instance',
        resource_group=f'integration:{integration_type}:{integration_instance_id}',
        parameters={
            'integration_type': integration_type,
            'integration_instance_id': integration_instance_id,
            'operation': 'runtime_refresh',
            'trigger_type': 'scheduled',
        },
        deduplication_key=deduplication_key,
        max_attempts=3,
    )
    if not created or not job.celery_task_id:
        return None
    created_at = datetime.now(UTC).isoformat()
    metadata = {
        'task_id': job.celery_task_id,
        'job_execution_id': job.id,
        'integration_type': integration_type,
        'operation': 'runtime_refresh',
        'integration_instance_id': integration_instance_id,
        'binding_id': None,
        'requested_by_user_id': None,
        'created_at': created_at,
        'status': 'info',
        'title': 'Runtime health refresh queued',
        'message': 'KAORI queued a lightweight runtime health refresh.',
        'detail': 'The runtime worker will process this provider independently.',
    }
    if not claim_validation_job(
        task_id=job.celery_task_id,
        integration_type=integration_type,
        operation='runtime_refresh',
        integration_instance_id=integration_instance_id,
        binding_id=None,
        metadata=metadata,
        conflicting_operations=('full_validation',),
    ):
        mark_job_failed(
            job.celery_task_id,
            error='Could not acquire the provider runtime lock.',
            error_code='resource_lock_conflict',
        )
        return None
    try:
        runtime_refresh_task = cast(Task, refresh_integration_runtime_instance)
        runtime_refresh_task.apply_async(
            kwargs={
                'integration_type': integration_type,
                'integration_instance_id': integration_instance_id,
                'requested_by_user_id': None,
                'trigger_type': 'scheduled',
                'job_execution_id': job.id,
            },
            task_id=job.celery_task_id,
            queue=_runtime_queue_name(),
            priority=job.priority,
        )
    except Exception as exc:
        release_validation_job(
            task_id=job.celery_task_id,
            integration_type=integration_type,
            operation='runtime_refresh',
            integration_instance_id=integration_instance_id,
        )
        mark_job_failed(job.celery_task_id, error=exc, error_code='dispatch_failed')
        raise
    return job.celery_task_id
