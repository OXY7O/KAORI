from __future__ import annotations

import logging

from flask import abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.common.http import is_htmx_request
from app.integrations.binding_service import SourceBindingSpec
from app.integrations.consumer_assets import get_consumer_asset_definition, resolve_consumer_asset
from app.integrations.observability.metrics_source.application.service import (
    create_metrics_binding,
    delete_metrics_binding,
    get_metrics_binding,
    rollback_metrics_source_transaction,
    update_metrics_binding_selector,
)
from app.integrations.observability.metrics_source.application.workspace_web import (
    instance_detail_context as _instance_detail_context,
)
from app.integrations.observability.metrics_source.application.workspace_web import (
    instance_or_404 as _instance_or_404,
)
from app.integrations.observability.metrics_source.application.workspace_web import (
    render_instance_partial as _render_instance_partial,
)
from app.integrations.validation.state import build_validation_snapshot
from app.integrations.validation.web import (
    enqueue_binding_validation,
    snapshot_feedback_for_user,
    validate_snapshot_access,
    validation_poll_response,
)
from app.platform_operations.notifications.service import record_operational_activity

logger = logging.getLogger(__name__)


def instance_binding_registry(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    context = _instance_detail_context(
        instance,
        binding_page=request.args.get('binding_page', 1, type=int) or 1,
        binding_per_page=request.args.get('binding_per_page', 5, type=int) or 5,
    )
    return render_template('integrations/observability/metrics_source/partials/_binding_registry.html', **context)


def add_instance_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    asset_type = (request.form.get('asset_type') or 'kubernetes_cluster').strip().lower()
    asset_key = (
        request.form.get('asset_key')
        or request.form.get('cluster_asset_key')
        or request.form.get('object_storage_asset_key')
        or ''
    ).strip()
    asset_definition = get_consumer_asset_definition(asset_type)
    asset = resolve_consumer_asset(asset_type, asset_key)
    asset_label = (
        str(getattr(asset, 'name', '') or asset_key)
        if asset is not None
        else asset_definition.label
        if asset_definition is not None
        else 'the selected consumer asset'
    )

    role = (request.form.get('binding_role') or 'primary').strip().lower()
    priority = request.form.get('priority', 100, type=int) or 100
    selector_label = request.form.get('selector_label', '').strip() or None
    selector_value = request.form.get('selector_value', '').strip() or None
    selector_operator = request.form.get('selector_operator', '=').strip() or '='
    query_horizon = request.form.get('query_horizon', 'balanced').strip().lower() or 'balanced'
    routing_weight = request.form.get('routing_weight', type=int)
    routing_weight = 100 if routing_weight is None else routing_weight
    routing_policy = {'query_horizon': query_horizon, 'weight': routing_weight}
    is_htmx = is_htmx_request()

    try:
        if asset_definition is None:
            raise ValueError('Select a supported managed asset type.')
        if asset is None:
            raise ValueError('Select an available managed asset.')
        binding = create_metrics_binding(
            instance=instance,
            spec=SourceBindingSpec(
                asset_type=asset_type,
                asset_key=str(asset_key),
                role=role,
                priority=priority,
                selector_label=selector_label,
                selector_value=selector_value,
                selector_operator=selector_operator,
                routing_policy=routing_policy,
            ),
        )
    except ValueError as exc:
        error = str(exc)
        operation_feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_create_rejected',
            status='error',
            title='Metrics Source binding not saved',
            message=f'KAORI could not bind {instance.name} to {asset_label}.',
            detail=error,
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source bindings',
            action_icon='waypoints',
            metadata={
                'instance_id': instance.id,
                'asset_type': asset_type,
                'asset_key': asset_key or None,
                'binding_role': role,
                'priority': priority,
                'selector_label': selector_label,
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        rollback_metrics_source_transaction()
        logger.exception('Metrics Source binding creation failed for instance %s.', instance_id)
        error = 'KAORI could not save the consumer binding. Review database connectivity and retry.'
        operation_feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_create_failed',
            status='error',
            title='Metrics Source binding not saved',
            message=f'KAORI could not bind {instance.name} to {asset_label}.',
            detail=error,
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source bindings',
            action_icon='waypoints',
            metadata={
                'instance_id': instance.id,
                'asset_type': asset_type,
                'asset_key': asset_key or None,
                'reason': type(exc).__name__,
            },
            queue_feedback=not is_htmx,
        )
    else:
        error = None
        operation_feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_created',
            status='success',
            title='Metrics Source binding created',
            message=f'{instance.name} is now available to {asset_label}.',
            detail=f'{role.title()} source with priority {priority}. Metrics identity: {selector_label or "unscoped"}.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source bindings',
            action_icon='waypoints',
            metadata={
                'instance_id': instance.id,
                'binding_id': binding.id,
                'asset_type': binding.asset_type,
                'asset_key': binding.asset_key,
                'selector_label': selector_label,
                'selector_value': selector_value,
            },
            queue_feedback=not is_htmx,
        )

    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_detail_scope.html',
            instance,
            operation_feedback=operation_feedback,
            binding_error=error,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#scope')


def update_instance_binding_selector(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = get_metrics_binding(instance, binding_id)
    if binding is None:
        abort(404)
    is_htmx = is_htmx_request()
    selector_label = request.form.get('selector_label', '').strip() or None
    selector_value = request.form.get('selector_value', '').strip() or None
    selector_operator = request.form.get('selector_operator', '=').strip() or '='
    query_horizon = request.form.get('query_horizon', 'balanced').strip().lower() or 'balanced'
    routing_weight = request.form.get('routing_weight', type=int)
    routing_weight = 100 if routing_weight is None else routing_weight
    routing_policy = {'query_horizon': query_horizon, 'weight': routing_weight}
    try:
        update_metrics_binding_selector(
            instance=instance,
            binding=binding,
            selector_label=selector_label,
            selector_value=selector_value,
            selector_operator=selector_operator,
            routing_policy=routing_policy,
        )
    except ValueError as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_selector_update_rejected',
            status='error',
            title='Metrics identity not updated',
            message='KAORI could not save the Metrics source binding selector.',
            detail=str(exc),
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='scan-line',
            metadata={'instance_id': instance.id, 'binding_id': binding.id},
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        rollback_metrics_source_transaction()
        logger.exception('Metrics Source binding selector update failed for binding %s.', binding_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_selector_update_failed',
            status='error',
            title='Metrics identity not updated',
            message='KAORI could not persist the Metrics source binding selector.',
            detail='Review KAORI logs and database connectivity before retrying.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='scan-line',
            metadata={'instance_id': instance.id, 'binding_id': binding.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_selector_updated',
            status='success',
            title='Metrics identity updated',
            message='The Metrics source binding selector was saved.',
            detail='Binding readiness returned to Validation Required. Validate the binding before operational use.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Validate binding',
            action_icon='scan-search',
            metadata={
                'instance_id': instance.id,
                'binding_id': binding.id,
                'selector_label': selector_label,
                'selector_operator': selector_operator,
                'selector_value': selector_value,
            },
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#scope')


def validate_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = get_metrics_binding(instance, binding_id)
    if binding is None:
        abort(404)
    is_htmx = is_htmx_request()
    try:
        validation_job, created = enqueue_binding_validation(
            integration_type='metrics_source',
            integration_instance_id=instance.integration_instance_id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='metrics_binding_validation_queued' if created else 'metrics_binding_validation_already_running',
            status='info' if created else 'warning',
            title='Metrics Source binding validation queued'
            if created
            else 'Metrics source binding validation already running',
            message=(
                'KAORI queued the metrics identity validation.'
                if created
                else 'The metrics identity validation is already running.'
            ),
            detail=(
                'The validation worker will execute the scope-isolated probe before this binding becomes eligible.'
                if created
                else 'KAORI kept the active task and did not enqueue a duplicate.'
            ),
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='scan-search',
            metadata={
                'task_id': validation_job.get('task_id'),
                'instance_id': instance.id,
                'binding_id': binding.id,
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Metrics source binding validation for %s.', binding_id)
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='metrics_binding_validation_enqueue_failed',
            status='error',
            title='Metrics Source binding validation not queued',
            message='KAORI could not queue the metrics identity validation.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'binding_id': binding.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
            binding_validation_job=validation_job,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#scope')


def binding_validation_status(instance_id: int, binding_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = get_metrics_binding(instance, binding_id)
    if binding is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='metrics_source',
        integration_instance_id=instance.integration_instance_id,
        binding_id=binding.id,
    ):
        abort(404)
    content = _render_instance_partial(
        'integrations/observability/metrics_source/partials/_detail_scope.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        binding_validation_job=snapshot,
    )
    return validation_poll_response(content, snapshot=snapshot)


def delete_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    binding = get_metrics_binding(instance, binding_id)
    if binding is None:
        abort(404)
    binding_metadata = {
        'instance_id': instance.id,
        'instance_name': instance.name,
        'binding_id': binding.id,
        'asset_type': binding.asset_type,
        'asset_key': binding.asset_key,
        'binding_role': binding.binding_role,
    }
    try:
        deleted_binding = delete_metrics_binding(instance, binding_id)
        if deleted_binding is None:
            abort(404)
    except SQLAlchemyError as exc:
        logger.exception('Metrics Source binding deletion failed for binding %s.', binding_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_delete_failed',
            status='error',
            title='Metrics Source binding not removed',
            message=f'KAORI could not remove the selected binding from {instance.name}.',
            detail='Review KAORI logs and database connectivity before retrying.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='waypoints',
            metadata={**binding_metadata, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_binding_deleted',
            status='success',
            title='Metrics Source binding removed',
            message=f'{instance.name} is no longer mapped to the selected managed cluster.',
            detail=f'{binding.asset_type}:{binding.asset_key} was removed.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='waypoints',
            metadata=binding_metadata,
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#scope')
