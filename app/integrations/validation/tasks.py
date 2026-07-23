from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

from celery import Task, shared_task
from flask import current_app

from app.extensions import db
from app.integrations.lifecycle import ensure_canonical_instance, ensure_provider_operational
from app.integrations.registry import execute_integration_operation, get_integration
from app.integrations.runtime.monitoring import refresh_and_record
from app.integrations.runtime.repository import persist_runtime_state
from app.integrations.validation.state import (
    claim_validation_job,
    get_active_validation_task_id,
    release_validation_job,
    store_validation_metadata,
)
from app.jobs.constants import WORKLOAD_RUNTIME
from app.jobs.fingerprint import build_deduplication_key
from app.jobs.service import (
    create_or_attach_job,
    get_job_by_task_id,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
    subscriber_user_ids,
    update_job_progress,
)
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding
from app.models.kubernetes import KubernetesConnection
from app.models.prometheus import PrometheusInstance
from app.notifications.service import record_operational_activity

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


def _runtime_queue_name() -> str:
    return (
        str(current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE') or 'integration-runtime').strip()
        or 'integration-runtime'
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


def _canceled_before_worker_start(task_id: str) -> bool:
    job = get_job_by_task_id(task_id)
    return bool(job and job.status in {'canceled', 'cancel_requested', 'expired'})


def _store_progress(task, metadata: dict[str, Any]) -> None:
    task_id = str(task.request.id)
    try:
        mark_job_running(task_id, message=str(metadata.get('message') or metadata.get('title') or 'Worker started'))
        update_job_progress(
            task_id,
            current=int(metadata.get('progress_current') or 0),
            total=int(metadata.get('progress_total') or 0),
            message=str(metadata.get('detail') or metadata.get('message') or 'Worker started'),
        )
    except Exception:
        db.session.rollback()
        logger.exception('Could not update canonical job progress for task %s.', task_id)
    try:
        task.update_state(state='PROGRESS', meta=metadata)
    except Exception:
        logger.exception('Could not publish validation progress for task %s.', task_id)
    _store_metadata_safely(task_id=task_id, metadata=metadata)


def _update_worker_phase(
    task,
    *,
    current: int,
    total: int,
    message: str,
) -> None:
    task_id = str(task.request.id)
    metadata = {
        'task_id': task_id,
        'status': 'info',
        'title': 'Worker operation in progress',
        'message': message,
        'detail': message,
        'progress_current': current,
        'progress_total': total,
    }
    try:
        update_job_progress(task_id, current=current, total=total, message=message)
        task.update_state(state='PROGRESS', meta=metadata)
    except Exception:
        db.session.rollback()
        logger.exception('Could not update worker phase for task %s.', task_id)
    _store_metadata_safely(task_id=task_id, metadata=metadata)


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


def _ensure_instance_operational(instance: Any, *, provider_type: str) -> None:
    """Compatibility wrapper around the shared integration lifecycle guard."""
    ensure_provider_operational(instance, provider_type=provider_type)


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
            state = get_integration('prometheus').adapter.get_state(instance)
        elif provider_type == 'alertmanager':
            instance = db.session.get(AlertmanagerInstance, instance_id)
            if instance is None:
                return
            state = get_integration('alertmanager').adapter.get_state(instance)
        elif provider_type == 'kubernetes':
            instance = db.session.get(KubernetesConnection, instance_id)
            if instance is None:
                return
            state = get_integration('kubernetes').adapter.get_state(instance)
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
    task_id = str(metadata.get('task_id') or '')
    job = get_job_by_task_id(task_id) if task_id else None
    user_ids = subscriber_user_ids(job) if job is not None else []
    if requested_by_user_id is not None and requested_by_user_id not in user_ids:
        user_ids.insert(0, requested_by_user_id)
    if not user_ids:
        return None
    section = (
        'scope'
        if operation == 'binding_validation'
        else ('runtime' if operation == 'runtime_refresh' else 'validation')
    )
    selected_feedback: dict[str, Any] | None = None
    enriched_metadata = {**metadata, 'job_execution_id': job.id if job is not None else None}
    for user_id in user_ids:
        feedback = record_operational_activity(
            user_id=user_id,
            event_type=f'{provider_type}_{operation}_completed'
            if status != 'error'
            else f'{provider_type}_{operation}_failed',
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url=_action_url(provider_type, instance_id, section=section),
            action_label='Review validation',
            action_icon='scan-search',
            metadata=enriched_metadata,
            queue_feedback=False,
        )
        if requested_by_user_id == user_id or selected_feedback is None:
            selected_feedback = feedback
    return selected_feedback


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
    payload = {
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
    task_id = str(base.get('task_id') or '')
    if task_id:
        try:
            if status == 'error':
                mark_job_failed(task_id, error=detail, error_code='operation_failed')
            else:
                mark_job_succeeded(
                    task_id,
                    result_summary=result or {},
                    result_type=str(base.get('operation') or 'job_result'),
                    partial=status == 'warning',
                )
        except Exception:
            db.session.rollback()
            logger.exception('Could not finalize canonical job record for task %s.', task_id)
    return payload


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
    job_execution_id: int | None = None,
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
        'job_execution_id': job_execution_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Integration validation running',
        'message': 'The validation worker is rebuilding operational evidence.',
        'detail': 'KAORI will update this workspace when the worker completes.',
        'progress_current': 1,
        'progress_total': 4,
    }
    if _canceled_before_worker_start(task_id):
        _release_job_safely(
            task_id=task_id,
            provider_type=provider_type,
            operation='full_validation',
            instance_id=instance_id,
        )
        return {
            **base,
            'status': 'warning',
            'title': 'Validation canceled',
            'message': 'KAORI canceled the queued validation before provider execution.',
            'detail': 'No provider request was started.',
            'finished_at': _now_iso(),
        }
    _store_progress(self, base)
    operation = str(base['operation'])
    try:
        _update_worker_phase(
            self, current=1, total=4, message='Connecting to the provider and loading the full validation contract.'
        )
        if provider_type == 'prometheus':
            instance = db.session.get(PrometheusInstance, instance_id)
            if instance is None:
                raise LookupError('Prometheus instance no longer exists.')
            _ensure_instance_operational(instance, provider_type='prometheus')
            validation_result, state, _ = refresh_and_record(
                get_integration('prometheus').adapter,
                instance,
                trigger_type=trigger_type,
            )
            _update_worker_phase(
                self,
                current=2,
                total=4,
                message='Prometheus capability evidence was collected; refreshing scope bindings.',
            )
            ensure_canonical_instance(instance, provider_type='prometheus')
            binding_summary = _refresh_prometheus_bindings(instance)
            _update_worker_phase(
                self, current=3, total=4, message='Prometheus scope bindings were refreshed; finalizing evidence.'
            )
            db.session.commit()
            result_payload = dict(validation_result or {})
            result_payload['binding_validation_summary'] = binding_summary
            readiness = str(result_payload.get('readiness_status') or state.readiness or 'validation_required')
            status = 'success' if readiness == 'ready' else ('error' if readiness == 'blocked' else 'warning')
            title = (
                'Prometheus validation completed' if status != 'error' else 'Prometheus validation requires attention'
            )
            message = f'Full Validation completed for {instance.name}.'
            detail = str(result_payload.get('message') or state.message)
            instance_name = instance.name
        elif provider_type == 'alertmanager':
            instance = db.session.get(AlertmanagerInstance, instance_id)
            if instance is None:
                raise LookupError('Alertmanager instance no longer exists.')
            _ensure_instance_operational(instance, provider_type='alertmanager')
            validation_result, state, _ = refresh_and_record(
                get_integration('alertmanager').adapter,
                instance,
                trigger_type=trigger_type,
            )
            _update_worker_phase(
                self,
                current=2,
                total=4,
                message='Alertmanager capability evidence was collected; refreshing scope bindings.',
            )
            ensure_canonical_instance(instance, provider_type='alertmanager')
            binding_summary = _refresh_alertmanager_bindings(instance)
            _update_worker_phase(
                self, current=3, total=4, message='Alertmanager scope bindings were refreshed; finalizing evidence.'
            )
            db.session.commit()
            result_payload = (
                validation_result.to_dict() if hasattr(validation_result, 'to_dict') else dict(validation_result or {})
            )
            result_payload['binding_validation_summary'] = binding_summary
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
                get_integration('kubernetes').adapter,
                connection,
                trigger_type=trigger_type,
            )
            _update_worker_phase(
                self,
                current=3,
                total=4,
                message='Kubernetes compatibility, capability, and RBAC evidence was collected; finalizing the result.',
            )
            result_payload = dict(validation_result or {})
            success = bool(result_payload.get('success'))
            status = 'success' if success and state.readiness == 'ready' else ('warning' if success else 'error')
            title = (
                'Kubernetes capability validation completed' if success else 'Kubernetes capability validation failed'
            )
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
        detail = str(exc) or 'Review runtime-worker logs, provider reachability, credentials, and Redis connectivity.'
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


def _refresh_prometheus_bindings(instance: PrometheusInstance) -> dict[str, Any]:
    if instance.integration_instance_id is None:
        return {'total': 0, 'ready': 0, 'attention': 0}
    bindings = (
        IntegrationBinding.query.filter_by(
            integration_instance_id=instance.integration_instance_id,
            enabled=True,
        )
        .order_by(IntegrationBinding.id.asc())
        .all()
    )
    ready = 0
    results: list[dict[str, Any]] = []
    for binding in bindings:
        result = execute_integration_operation(
            'prometheus',
            'binding.validate',
            instance=instance,
            binding=binding,
            commit=False,
        )
        if result.get('status') == 'ready':
            ready += 1
        results.append(
            {
                'binding_id': binding.id,
                'status': result.get('status'),
                'matched_signal': result.get('matched_signal'),
                'matched_series': result.get('matched_series'),
            }
        )
    return {
        'total': len(bindings),
        'ready': ready,
        'attention': len(bindings) - ready,
        'results': results,
    }


def _refresh_alertmanager_bindings(instance: AlertmanagerInstance) -> dict[str, Any]:
    if instance.integration_instance_id is None:
        return {'total': 0, 'ready': 0, 'attention': 0}
    bindings = (
        IntegrationBinding.query.filter_by(
            integration_instance_id=instance.integration_instance_id,
            enabled=True,
        )
        .order_by(IntegrationBinding.id.asc())
        .all()
    )
    ready = 0
    results: list[dict[str, Any]] = []
    for binding in bindings:
        result = execute_integration_operation(
            'alertmanager',
            'binding.validate',
            instance=instance,
            binding=binding,
            commit=False,
        )
        if result.get('status') == 'ready':
            ready += 1
        results.append(
            {
                'binding_id': binding.id,
                'status': result.get('status'),
                'matched_alerts': result.get('matched_alerts'),
            }
        )
    return {
        'total': len(bindings),
        'ready': ready,
        'attention': len(bindings) - ready,
        'results': results,
    }


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
    job_execution_id: int | None = None,
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
        'job_execution_id': job_execution_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Binding validation running',
        'message': 'The validation worker is checking the scope selector.',
        'detail': 'Operational source resolution remains blocked until this job completes.',
        'progress_current': 1,
        'progress_total': 3,
    }
    if _canceled_before_worker_start(task_id):
        _release_job_safely(
            task_id=task_id,
            provider_type=provider_type,
            operation='binding_validation',
            instance_id=instance_id,
            binding_id=binding_id,
        )
        return {
            **base,
            'status': 'warning',
            'title': 'Binding validation canceled',
            'message': 'KAORI canceled the queued binding validation before provider execution.',
            'detail': 'No provider request was started.',
            'finished_at': _now_iso(),
        }
    _store_progress(self, base)
    try:
        _update_worker_phase(self, current=1, total=3, message='Loading the binding and its scope identity contract.')
        binding = db.session.get(IntegrationBinding, binding_id)
        if binding is None:
            raise LookupError('Integration binding no longer exists.')
        module = get_integration(provider_type)
        if 'binding.validate' not in module.operations:
            raise ValueError(f'{module.label} does not support binding validation.')
        instance = module.get_instance(instance_id)
        _ensure_instance_operational(instance, provider_type=provider_type)
        if not binding.enabled:
            raise RuntimeError('Binding validation was canceled because the binding is disabled.')
        if binding.integration_instance_id != instance.integration_instance_id:
            raise LookupError(f'{module.label} binding does not belong to the selected source.')
        result_payload = execute_integration_operation(
            provider_type,
            'binding.validate',
            instance=instance,
            binding=binding,
        )
        instance_name = instance.name

        _update_worker_phase(
            self, current=2, total=3, message='The provider accepted the binding probe; finalizing scope evidence.'
        )
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
    job_execution_id: int | None = None,
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
        'job_execution_id': job_execution_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Runtime health refresh running',
        'message': 'KAORI is refreshing lightweight provider health evidence.',
        'detail': 'Full capability evidence is preserved.',
        'progress_current': 1,
        'progress_total': 3,
    }
    if _canceled_before_worker_start(task_id):
        _release_job_safely(
            task_id=task_id,
            provider_type=provider_type,
            operation='runtime_refresh',
            instance_id=instance_id,
        )
        return {
            **base,
            'status': 'warning',
            'title': 'Runtime refresh canceled',
            'message': 'KAORI canceled the queued runtime refresh before provider execution.',
            'detail': 'No provider request was started.',
            'finished_at': _now_iso(),
        }
    _store_progress(self, base)
    try:
        _update_worker_phase(
            self, current=1, total=3, message='Connecting to the provider for a lightweight runtime health check.'
        )
        integration = get_integration(provider_type)
        instance = integration.get_instance(instance_id)
        _ensure_instance_operational(instance, provider_type=provider_type)
        result_payload = integration.execute('runtime.health', instance)
        state = integration.adapter.get_state(instance, validation_result=result_payload)
        persist_runtime_state(
            state,
            trigger_type=trigger_type,
            integration_instance_id=instance.integration_instance_id,
        )
        _update_worker_phase(
            self, current=2, total=3, message='Runtime health evidence was collected; persisting the observation.'
        )
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
        detail = str(exc) or 'Review runtime-worker logs, provider reachability, credentials, and Redis connectivity.'
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
    deduplication_key = build_deduplication_key('integration', provider_type, instance_id, 'runtime_refresh')
    job, created = create_or_attach_job(
        job_type='integration_operation',
        operation='runtime_refresh',
        queue_name=_runtime_queue_name(),
        workload_class=WORKLOAD_RUNTIME,
        requested_by_user_id=None,
        provider_type=provider_type,
        provider_instance_id=instance_id,
        scope_type='integration_instance',
        resource_group=f'integration:{provider_type}:{instance_id}',
        parameters={
            'provider_type': provider_type,
            'instance_id': instance_id,
            'operation': 'runtime_refresh',
            'trigger_type': 'scheduled',
        },
        deduplication_key=deduplication_key,
        max_attempts=3,
    )
    if not created or not job.celery_task_id:
        return None
    created_at = _now_iso()
    metadata = {
        'task_id': job.celery_task_id,
        'job_execution_id': job.id,
        'provider_type': provider_type,
        'operation': 'runtime_refresh',
        'instance_id': instance_id,
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
        provider_type=provider_type,
        operation='runtime_refresh',
        instance_id=instance_id,
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
                'provider_type': provider_type,
                'instance_id': instance_id,
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
            provider_type=provider_type,
            operation='runtime_refresh',
            instance_id=instance_id,
        )
        mark_job_failed(job.celery_task_id, error=exc, error_code='dispatch_failed')
        raise
    return job.celery_task_id
