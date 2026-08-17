from __future__ import annotations

from typing import Any

from celery.exceptions import CeleryError
from flask import current_app, request, url_for
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.validation.web import enqueue_instance_validation, enqueue_runtime_health_refresh
from app.minio.presentation import MinioDetailQuery
from app.models.minio import MinioInstance
from app.notifications.service import record_operational_activity


def detail_query_from_request() -> MinioDetailQuery:
    return MinioDetailQuery(
        capability_query=request.args.get('capability_q', '').strip(),
        capability_requirement=request.args.get('capability_requirement', '').strip(),
        capability_status=request.args.get('capability_status', '').strip(),
        capability_page=request.args.get('capability_page', 1, type=int) or 1,
        capability_per_page=request.args.get('capability_per_page', 5, type=int) or 5,
        binding_page=request.args.get('binding_page', 1, type=int) or 1,
        binding_per_page=request.args.get('binding_per_page', 5, type=int) or 5,
        history_page=request.args.get('page', 1, type=int) or 1,
        history_per_page=request.args.get('per_page', 5, type=int) or 5,
        history_trigger=request.args.get('history_trigger', '').strip(),
        history_health=request.args.get('history_health', '').strip(),
        history_readiness=request.args.get('history_readiness', '').strip(),
    )


def queue_full_validation(
    instance: MinioInstance,
    *,
    user_id: int,
    is_htmx: bool,
) -> tuple[dict[str, Any] | None, Any]:
    validation_job: dict[str, Any] | None = None
    try:
        validation_job, created = enqueue_instance_validation(
            integration_type='object_storage',
            integration_instance_id=instance.integration_instance_id,
            requested_by_user_id=user_id,
        )
        feedback = record_operational_activity(
            user_id=user_id,
            event_type='minio_validation_queued' if created else 'minio_validation_already_running',
            status='info' if created else 'warning',
            title='MinIO Validation Queued' if created else 'MinIO Validation Already Running',
            message=(
                f'KAORI queued Full Validation for {instance.name}.'
                if created
                else f'A Full Validation job is already running for {instance.name}.'
            ),
            detail=(
                'The worker will refresh S3 API, compatibility, and provider capability evidence.'
                if created
                else 'KAORI kept the active validation job and did not enqueue a duplicate.'
            ),
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='validation'),
            action_label='Review MinIO validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'task_id': validation_job.get('task_id')},
            queue_feedback=not is_htmx,
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        feedback = record_operational_activity(
            user_id=user_id,
            event_type='minio_validation_queue_failed',
            status='error',
            title='MinIO Validation Could Not Start',
            message=f'KAORI could not queue Full Validation for {instance.name}.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance.id),
            action_label='Review MinIO validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    return validation_job, feedback


def queue_runtime_refresh(
    instance: MinioInstance,
    *,
    user_id: int,
    is_htmx: bool,
) -> tuple[dict[str, Any] | None, Any]:
    runtime_refresh_job: dict[str, Any] | None = None
    try:
        runtime_refresh_job, created = enqueue_runtime_health_refresh(
            integration_type='object_storage',
            integration_instance_id=instance.integration_instance_id,
            requested_by_user_id=user_id,
        )
        feedback = record_operational_activity(
            user_id=user_id,
            event_type='minio_runtime_refresh_queued' if created else 'minio_runtime_refresh_already_running',
            status='info' if created else 'warning',
            title='MinIO Runtime Refresh Queued' if created else 'MinIO Runtime Refresh Already Running',
            message=(
                f'KAORI queued a lightweight runtime refresh for {instance.name}.'
                if created
                else f'A runtime refresh is already running for {instance.name}.'
            ),
            detail=(
                'The runtime worker will refresh MinIO endpoint health without rebuilding consumer binding evidence.'
                if created
                else 'KAORI kept the active task and did not enqueue a duplicate.'
            ),
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='runtime'),
            action_label='Review MinIO runtime',
            action_icon='activity',
            metadata={
                'task_id': runtime_refresh_job.get('task_id'),
                'instance_id': instance.id,
                'queue': current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime'),
            },
            queue_feedback=not is_htmx,
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        feedback = record_operational_activity(
            user_id=user_id,
            event_type='minio_runtime_refresh_enqueue_failed',
            status='error',
            title='MinIO Runtime Refresh Not Queued',
            message=f'KAORI could not queue runtime health refresh for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-runtime worker before retrying.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='runtime'),
            action_label='Review MinIO runtime',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    return runtime_refresh_job, feedback
