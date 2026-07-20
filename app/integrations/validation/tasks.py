from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from celery import shared_task
from flask import current_app

from app.alertmanager.runtime_adapter import runtime_adapter as alertmanager_runtime_adapter
from app.alertmanager.service import (
    refresh_alertmanager_runtime_health,
    validate_alertmanager_binding,
)
from app.extensions import db
from app.integrations.lifecycle import ensure_canonical_instance
from app.integrations.runtime.kubernetes_adapter import runtime_adapter as kubernetes_runtime_adapter
from app.integrations.runtime.monitoring import refresh_and_record
from app.integrations.runtime.repository import persist_runtime_state
from app.integrations.validation.state import (
    claim_validation_job,
    get_active_validation_task_id,
    release_validation_job,
    store_validation_metadata,
)
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, KubernetesConnection
from app.models.prometheus import PrometheusInstance
from app.notifications.service import record_operational_activity
from app.prometheus.runtime_adapter import runtime_adapter as prometheus_runtime_adapter
from app.prometheus.service import PrometheusService, validate_prometheus_binding

logger = logging.getLogger(__name__)

INSTANCE_VALIDATION_TASK_NAME = 'app.integrations.validation.tasks.validate_integration_instance'
BINDING_VALIDATION_TASK_NAME = 'app.integrations.validation.tasks.validate_integration_binding'
RUNTIME_REFRESH_TASK_NAME = 'app.integrations.validation.tasks.refresh_integration_runtime_instance'
VALIDATION_QUEUE_DEFAULT = 'integration-validation'


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _queue_name() -> str:
    return (
        str(current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE') or VALIDATION_QUEUE_DEFAULT).strip()
        or VALIDATION_QUEUE_DEFAULT
    )


def _action_url(provider_type: str, instance_id: int, *, section: str) -> str:
    if provider_type == 'prometheus':
        return f'/integrations/prometheus/instances/{instance_id}#{section}'
    if provider_type == 'alertmanager':
        return f'/integrations/alertmanager/instances/{instance_id}#{section}'
    if provider_type == 'kubernetes':
        connection = db.session.get(KubernetesConnection, instance_id)
        cluster_id = connection.cluster_id if connection is not None else str(instance_id)
        return f'/integrations/kubernetes/{cluster_id}#{section}'
    return '/integrations/'


def _store_metadata_safely(*, task_id: str, metadata: dict[str, Any]) -> None:
    try:
        store_validation_metadata(task_id=task_id, metadata=metadata)
    except Exception:
        logger.exception('Could not persist validation metadata for task %s.', task_id)


def _store_progress(task, metadata: dict[str, Any]) -> None:
    try:
        task.update_state(state='PROGRESS', meta=metadata)
    except Exception:
        logger.exception('Could not publish validation progress for task %s.', task.request.id)
    _store_metadata_safely(task_id=str(task.request.id), metadata=metadata)


def _release_job_safely(
    *,
    task_id: str,
    provider_type: str,
    operation: str,
    instance_id: int,
    binding_id: int | None = None,
) -> None:
    try:
        release_validation_job(
            task_id=task_id,
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
            binding_id=binding_id,
        )
    except Exception:
        logger.exception(
            'Could not release validation lock for %s %s instance %s binding %s.',
            provider_type,
            operation,
            instance_id,
            binding_id,
        )


def _persist_failure_observation(
    *,
    provider_type: str,
    instance_id: int,
    trigger_type: str,
    error: Exception,
) -> None:
    """Best-effort persistence for failed runtime or validation attempts."""
    try:
        if provider_type == 'prometheus':
            instance = db.session.get(PrometheusInstance, instance_id)
            if instance is None:
                return
            instance.last_checked_at = datetime.now(UTC)
            instance.last_status = 'disconnected'
            instance.last_error = str(error)[:1000]
            instance.last_response_time_ms = None
            db.session.commit()
            state = prometheus_runtime_adapter.get_state(instance)
        elif provider_type == 'alertmanager':
            instance = db.session.get(AlertmanagerInstance, instance_id)
            if instance is None:
                return
            state = alertmanager_runtime_adapter.get_state(instance)
        elif provider_type == 'kubernetes':
            instance = db.session.get(KubernetesConnection, instance_id)
            if instance is None:
                return
            state = kubernetes_runtime_adapter.get_state(instance)
        else:
            return
        persist_runtime_state(
            state,
            trigger_type=trigger_type,
            integration_instance_id=instance.integration_instance_id,
        )
    except Exception:
        db.session.rollback()
        logger.exception(
            'Could not persist failed runtime observation for %s instance %s.',
            provider_type,
            instance_id,
        )


def _record_completion(
    *,
    requested_by_user_id: int | None,
    provider_type: str,
    instance_id: int,
    operation: str,
    status: str,
    title: str,
    message: str,
    detail: str,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    if requested_by_user_id is None:
        return None
    section = 'scope' if operation == 'binding_validation' else ('runtime' if operation == 'runtime_refresh' else 'validation')
    return record_operational_activity(
        user_id=requested_by_user_id,
        event_type=f'{provider_type}_{operation}_completed' if status != 'error' else f'{provider_type}_{operation}_failed',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=_action_url(provider_type, instance_id, section=section),
        action_label='Review validation',
        action_icon='scan-search',
        metadata=metadata,
        queue_feedback=False,
    )


def _final_payload(
    *,
    base: dict[str, Any],
    status: str,
    title: str,
    message: str,
    detail: str,
    feedback: dict[str, Any] | None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finished_at = _now_iso()
    started = datetime.fromisoformat(str(base['started_at']))
    finished = datetime.fromisoformat(finished_at)
    return {
        **base,
        'status': status,
        'title': title,
        'message': message,
        'detail': detail,
        'feedback': feedback,
        'result': result or {},
        'finished_at': finished_at,
        'duration_seconds': max(int((finished - started).total_seconds()), 0),
    }


@shared_task(
    bind=True,
    name=INSTANCE_VALIDATION_TASK_NAME,
    acks_late=True,
    reject_on_worker_lost=True,
)
def validate_integration_instance(
    self,
    *,
    provider_type: str,
    instance_id: int,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> dict[str, Any]:
    task_id = str(self.request.id)
    started_at = _now_iso()
    base = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': 'full_validation',
        'instance_id': instance_id,
        'binding_id': None,
        'requested_by_user_id': requested_by_user_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Integration validation running',
        'message': 'The validation worker is rebuilding operational evidence.',
        'detail': 'KAORI will update this workspace when the worker completes.',
    }
    _store_progress(self, base)
    operation = str(base['operation'])
    try:
        if provider_type == 'prometheus':
            instance = db.session.get(PrometheusInstance, instance_id)
            if instance is None:
                raise LookupError('Prometheus instance no longer exists.')
            validation_result, state, _ = refresh_and_record(
                prometheus_runtime_adapter,
                instance,
                trigger_type=trigger_type,
            )
            ensure_canonical_instance(instance, provider_type='prometheus')
            db.session.commit()
            result_payload = dict(validation_result or {})
            readiness = str(result_payload.get('readiness_status') or state.readiness or 'validation_required')
            status = 'success' if readiness == 'ready' else ('error' if readiness == 'blocked' else 'warning')
            title = 'Prometheus validation completed' if status != 'error' else 'Prometheus validation requires attention'
            message = f'Full Validation completed for {instance.name}.'
            detail = str(result_payload.get('message') or state.message)
            instance_name = instance.name
        elif provider_type == 'alertmanager':
            instance = db.session.get(AlertmanagerInstance, instance_id)
            if instance is None:
                raise LookupError('Alertmanager instance no longer exists.')
            validation_result, state, _ = refresh_and_record(
                alertmanager_runtime_adapter,
                instance,
                trigger_type=trigger_type,
            )
            result_payload = validation_result.to_dict() if hasattr(validation_result, 'to_dict') else dict(validation_result or {})
            readiness = str(result_payload.get('readiness_status') or state.readiness or 'validation_required')
            connected = bool(result_payload.get('connected'))
            status = 'success' if connected and readiness == 'ready' else ('warning' if connected else 'error')
            title = 'Alertmanager validation completed' if connected else 'Alertmanager validation failed'
            message = (
                f'{instance.name} capability evidence was rebuilt.'
                if connected
                else f'KAORI could not validate {instance.name}.'
            )
            detail = str(result_payload.get('reason') or result_payload.get('error') or state.message)
            instance_name = instance.name
        elif provider_type == 'kubernetes':
            connection = db.session.get(KubernetesConnection, instance_id)
            if connection is None:
                raise LookupError('Kubernetes connection no longer exists.')
            validation_result, state, _ = refresh_and_record(
                kubernetes_runtime_adapter,
                connection,
                trigger_type=trigger_type,
            )
            result_payload = dict(validation_result or {})
            success = bool(result_payload.get('success'))
            status = 'success' if success and state.readiness == 'ready' else ('warning' if success else 'error')
            title = 'Kubernetes capability validation completed' if success else 'Kubernetes capability validation failed'
            message = f'Compatibility, capability, and RBAC evidence was rebuilt for {connection.cluster.name}.'
            detail = str(result_payload.get('validation_message') or result_payload.get('message') or state.message)
            instance_name = connection.cluster.name
        else:
            raise ValueError(f'Unsupported integration provider: {provider_type}')

        completion_metadata = {
            'task_id': task_id,
            'provider_type': provider_type,
            'operation': operation,
            'instance_id': instance_id,
            'instance_name': instance_name,
            'readiness_status': result_payload.get('readiness_status'),
            'trigger_type': trigger_type,
        }
        feedback = _record_completion(
            requested_by_user_id=requested_by_user_id,
            provider_type=provider_type,
            instance_id=instance_id,
            operation=operation,
            status=status,
            title=title,
            message=message,
            detail=detail,
            metadata=completion_metadata,
        )
        payload = _final_payload(
            base=base,
            status=status,
            title=title,
            message=message,
            detail=detail,
            feedback=feedback,
            result=result_payload,
        )
        _store_metadata_safely(task_id=task_id, metadata=payload)
        return payload
    except Exception as exc:
        db.session.rollback()
        _persist_failure_observation(
            provider_type=provider_type,
            instance_id=instance_id,
            trigger_type=trigger_type,
            error=exc,
        )
        logger.exception('%s validation task failed for instance %s.', provider_type, instance_id)
        detail = str(exc) or 'Review validation-worker logs, provider reachability, credentials, and Redis connectivity.'
        feedback = _record_completion(
            requested_by_user_id=requested_by_user_id,
            provider_type=provider_type,
            instance_id=instance_id,
            operation=operation,
            status='error',
            title='Integration validation failed',
            message=f'KAORI could not complete the {provider_type.title()} validation job.',
            detail=detail,
            metadata={
                'task_id': task_id,
                'provider_type': provider_type,
                'operation': operation,
                'instance_id': instance_id,
                'reason': type(exc).__name__,
                'trigger_type': trigger_type,
            },
        )
        payload = _final_payload(
            base=base,
            status='error',
            title='Integration validation failed',
            message=f'KAORI could not complete the {provider_type.title()} validation job.',
            detail=detail,
            feedback=feedback,
        )
        _store_metadata_safely(task_id=task_id, metadata=payload)
        return payload
    finally:
        _release_job_safely(
            task_id=task_id,
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
        )


@shared_task(
    bind=True,
    name=BINDING_VALIDATION_TASK_NAME,
    acks_late=True,
    reject_on_worker_lost=True,
)
def validate_integration_binding(
    self,
    *,
    provider_type: str,
    instance_id: int,
    binding_id: int,
    requested_by_user_id: int | None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    started_at = _now_iso()
    base = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': 'binding_validation',
        'instance_id': instance_id,
        'binding_id': binding_id,
        'requested_by_user_id': requested_by_user_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Binding validation running',
        'message': 'The validation worker is checking the scope selector.',
        'detail': 'Operational source resolution remains blocked until this job completes.',
    }
    _store_progress(self, base)
    try:
        binding = db.session.get(IntegrationBinding, binding_id)
        if binding is None:
            raise LookupError('Integration binding no longer exists.')
        if provider_type == 'prometheus':
            instance = db.session.get(PrometheusInstance, instance_id)
            if instance is None or binding.integration_instance_id != instance.integration_instance_id:
                raise LookupError('Prometheus binding does not belong to the selected source.')
            result_payload = validate_prometheus_binding(instance=instance, binding=binding)
            instance_name = instance.name
        elif provider_type == 'alertmanager':
            instance = db.session.get(AlertmanagerInstance, instance_id)
            if instance is None or binding.integration_instance_id != instance.integration_instance_id:
                raise LookupError('Alertmanager binding does not belong to the selected source.')
            result_payload = validate_alertmanager_binding(instance=instance, binding=binding)
            instance_name = instance.name
        else:
            raise ValueError(f'Unsupported binding provider: {provider_type}')

        binding_status = str(result_payload.get('status') or 'validation_required')
        status = 'success' if binding_status == 'ready' else ('error' if binding_status == 'blocked' else 'warning')
        title = f'{provider_type.title()} binding validation completed'
        message = str(result_payload.get('message') or 'Binding validation completed.')
        detail = f'Binding status: {binding_status.replace("_", " ").title()}.'
        feedback = _record_completion(
            requested_by_user_id=requested_by_user_id,
            provider_type=provider_type,
            instance_id=instance_id,
            operation='binding_validation',
            status=status,
            title=title,
            message=message,
            detail=detail,
            metadata={
                'task_id': task_id,
                'provider_type': provider_type,
                'operation': 'binding_validation',
                'instance_id': instance_id,
                'instance_name': instance_name,
                'binding_id': binding_id,
                **result_payload,
            },
        )
        payload = _final_payload(
            base=base,
            status=status,
            title=title,
            message=message,
            detail=detail,
            feedback=feedback,
            result=result_payload,
        )
        _store_metadata_safely(task_id=task_id, metadata=payload)
        return payload
    except Exception as exc:
        db.session.rollback()
        logger.exception('%s binding validation task failed for binding %s.', provider_type, binding_id)
        detail = str(exc) or 'Review validation-worker logs and the source selector before retrying.'
        feedback = _record_completion(
            requested_by_user_id=requested_by_user_id,
            provider_type=provider_type,
            instance_id=instance_id,
            operation='binding_validation',
            status='error',
            title='Binding validation failed',
            message=f'KAORI could not validate the {provider_type.title()} scope binding.',
            detail=detail,
            metadata={
                'task_id': task_id,
                'provider_type': provider_type,
                'operation': 'binding_validation',
                'instance_id': instance_id,
                'binding_id': binding_id,
                'reason': type(exc).__name__,
            },
        )
        payload = _final_payload(
            base=base,
            status='error',
            title='Binding validation failed',
            message=f'KAORI could not validate the {provider_type.title()} scope binding.',
            detail=detail,
            feedback=feedback,
        )
        _store_metadata_safely(task_id=task_id, metadata=payload)
        return payload
    finally:
        _release_job_safely(
            task_id=task_id,
            provider_type=provider_type,
            operation='binding_validation',
            instance_id=instance_id,
            binding_id=binding_id,
        )


@shared_task(
    bind=True,
    name=RUNTIME_REFRESH_TASK_NAME,
    acks_late=True,
    reject_on_worker_lost=True,
)
def refresh_integration_runtime_instance(
    self,
    *,
    provider_type: str,
    instance_id: int,
    requested_by_user_id: int | None = None,
    trigger_type: str = 'scheduled',
) -> dict[str, Any]:
    task_id = str(self.request.id)
    started_at = _now_iso()
    base = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': 'runtime_refresh',
        'instance_id': instance_id,
        'binding_id': None,
        'requested_by_user_id': requested_by_user_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Runtime health refresh running',
        'message': 'KAORI is refreshing lightweight provider health evidence.',
        'detail': 'Full capability evidence is preserved.',
    }
    _store_progress(self, base)
    try:
        if provider_type == 'prometheus':
            instance = db.session.get(PrometheusInstance, instance_id)
            if instance is None:
                raise LookupError('Prometheus instance no longer exists.')
            result_payload = PrometheusService(instance).refresh_runtime_health()
            state = prometheus_runtime_adapter.get_state(instance, validation_result=result_payload)
            persist_runtime_state(
                state,
                trigger_type=trigger_type,
                integration_instance_id=instance.integration_instance_id,
            )
        elif provider_type == 'alertmanager':
            instance = db.session.get(AlertmanagerInstance, instance_id)
            if instance is None:
                raise LookupError('Alertmanager instance no longer exists.')
            result_payload = refresh_alertmanager_runtime_health(instance)
            state = alertmanager_runtime_adapter.get_state(instance)
            persist_runtime_state(
                state,
                trigger_type=trigger_type,
                integration_instance_id=instance.integration_instance_id,
            )
        elif provider_type == 'kubernetes':
            instance = db.session.get(KubernetesConnection, instance_id)
            if instance is None:
                raise LookupError('Kubernetes connection no longer exists.')
            result_payload = kubernetes_runtime_adapter.refresh_health(instance)
            state = kubernetes_runtime_adapter.get_state(instance, validation_result=result_payload)
            persist_runtime_state(
                state,
                trigger_type=trigger_type,
                integration_instance_id=instance.integration_instance_id,
            )
        else:
            raise ValueError(f'Unsupported integration provider: {provider_type}')
        completion_status = (
            'success'
            if state.health.status == 'healthy'
            else ('warning' if state.health.status == 'degraded' else 'error')
        )
        completion_result = {
            'health_status': state.health.status,
            'health_score': state.health.score,
            'readiness_status': state.readiness,
        }
        feedback = _record_completion(
            requested_by_user_id=requested_by_user_id,
            provider_type=provider_type,
            instance_id=instance_id,
            operation='runtime_refresh',
            status=completion_status,
            title='Runtime health refresh completed',
            message=f'{provider_type.title()} runtime health is {state.health.status}.',
            detail=state.message,
            metadata={
                'task_id': task_id,
                'provider_type': provider_type,
                'operation': 'runtime_refresh',
                'instance_id': instance_id,
                'trigger_type': trigger_type,
                **completion_result,
            },
        )
        payload = _final_payload(
            base=base,
            status=completion_status,
            title='Runtime health refresh completed',
            message=f'{provider_type.title()} runtime health is {state.health.status}.',
            detail=state.message,
            feedback=feedback,
            result=completion_result,
        )
        _store_metadata_safely(task_id=task_id, metadata=payload)
        return payload
    except Exception as exc:
        db.session.rollback()
        _persist_failure_observation(
            provider_type=provider_type,
            instance_id=instance_id,
            trigger_type=trigger_type,
            error=exc,
        )
        logger.exception('Runtime refresh failed for %s instance %s.', provider_type, instance_id)
        detail = str(exc) or 'Review validation-worker logs, provider reachability, credentials, and Redis connectivity.'
        feedback = _record_completion(
            requested_by_user_id=requested_by_user_id,
            provider_type=provider_type,
            instance_id=instance_id,
            operation='runtime_refresh',
            status='error',
            title='Runtime health refresh failed',
            message=f'KAORI could not refresh {provider_type.title()} runtime health.',
            detail=detail,
            metadata={
                'task_id': task_id,
                'provider_type': provider_type,
                'operation': 'runtime_refresh',
                'instance_id': instance_id,
                'trigger_type': trigger_type,
                'reason': type(exc).__name__,
            },
        )
        payload = _final_payload(
            base=base,
            status='error',
            title='Runtime health refresh failed',
            message=f'KAORI could not refresh {provider_type.title()} runtime health.',
            detail=detail,
            feedback=feedback,
        )
        _store_metadata_safely(task_id=task_id, metadata=payload)
        return payload
    finally:
        _release_job_safely(
            task_id=task_id,
            provider_type=provider_type,
            operation='runtime_refresh',
            instance_id=instance_id,
        )


def enqueue_runtime_refresh(*, provider_type: str, instance_id: int) -> str | None:
    if get_active_validation_task_id(
        provider_type=provider_type,
        operation='full_validation',
        instance_id=instance_id,
    ):
        return None
    active_task_id = get_active_validation_task_id(
        provider_type=provider_type,
        operation='runtime_refresh',
        instance_id=instance_id,
    )
    if active_task_id:
        return None
    task_id = str(uuid4())
    created_at = _now_iso()
    metadata = {
        'task_id': task_id,
        'provider_type': provider_type,
        'operation': 'runtime_refresh',
        'instance_id': instance_id,
        'binding_id': None,
        'requested_by_user_id': None,
        'created_at': created_at,
        'status': 'info',
        'title': 'Runtime health refresh queued',
        'message': 'KAORI queued a lightweight runtime health refresh.',
        'detail': 'The validation worker will process this provider independently.',
    }
    if not claim_validation_job(
        task_id=task_id,
        provider_type=provider_type,
        operation='runtime_refresh',
        instance_id=instance_id,
        binding_id=None,
        metadata=metadata,
        conflicting_operations=('full_validation',),
    ):
        return None
    try:
        refresh_integration_runtime_instance.apply_async(
            kwargs={
                'provider_type': provider_type,
                'instance_id': instance_id,
                'requested_by_user_id': None,
                'trigger_type': 'scheduled',
            },
            task_id=task_id,
            queue=_queue_name(),
        )
    except Exception:
        release_validation_job(
            task_id=task_id,
            provider_type=provider_type,
            operation='runtime_refresh',
            instance_id=instance_id,
        )
        raise
    return task_id
