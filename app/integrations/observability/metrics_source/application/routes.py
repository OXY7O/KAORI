from __future__ import annotations

import logging

from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.common.http import is_htmx_request
from app.integrations.capability_registry import build_capability_registry_view
from app.integrations.deletion import DeletionBlocked
from app.integrations.observability.metrics_source.application import binding_web
from app.integrations.observability.metrics_source.application.edit_web import edit_instance_response
from app.integrations.observability.metrics_source.application.forms import MetricsSourceForm
from app.integrations.observability.metrics_source.application.service import (
    remove_metrics_source,
    rollback_metrics_source_transaction,
    test_and_persist_metrics_source,
    test_metrics_source_connection,
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
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.validation.state import build_validation_snapshot
from app.integrations.validation.web import (
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
)
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)

logger = logging.getLogger(__name__)


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response


metrics_bp = Blueprint(
    'metrics',
    __name__,
    url_prefix='/integrations/metrics-sources',
)


@metrics_bp.post('/instances/<int:instance_id>/test-configuration')
@permission_required('integrations.manage')
def test_instance_configuration(instance_id: int) -> ResponseReturnValue:
    """Test submitted edit settings without persisting them."""
    instance = _instance_or_404(instance_id)
    form = MetricsSourceForm()
    setattr(form, '_existing_instance', instance)
    if not form.validate_on_submit():
        result = {'connected': False}
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_connection_test_failed',
            status='error',
            title='Metrics Source configuration test failed',
            message=f'Review the submitted settings for {instance.name}.',
            detail='The edited connection form did not satisfy the Metrics Source connection contract.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#configuration',
            action_label='Review Metrics Source configuration',
            action_icon='settings-2',
            metadata={
                'instance_id': instance.id,
                'fields': sorted(form.errors),
                'draft_update': True,
            },
            queue_feedback=False,
        )
    else:
        result = test_metrics_source_connection(form.to_configuration_input(), existing_instance=instance)
        connected = bool(result.get('connected'))
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_connection_test' if connected else 'metrics_source_connection_test_failed',
            status='success' if connected else 'error',
            title='Metrics Source configuration verified' if connected else 'Metrics source configuration test failed',
            message=(
                f'KAORI reached the submitted settings for {instance.name}.'
                if connected
                else f'KAORI could not verify the submitted settings for {instance.name}.'
            ),
            detail=(
                f'{str(result.get("endpoint_product") or "metrics source").title()} '
                f'{result.get("version") or "unknown"} responded in {result.get("response_time_ms") or 0} ms. '
                'Save the configuration, then run Full Validation.'
                if connected
                else result.get('error')
                or result.get('reason')
                or 'Review endpoint, authentication, TLS, and network reachability.'
            ),
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#configuration',
            action_label='Review Metrics Source configuration',
            action_icon='settings-2',
            metadata={
                'instance_id': instance.id,
                'endpoint_host': result.get('endpoint_host'),
                'endpoint_product': result.get('endpoint_product'),
                'version': result.get('version'),
                'compatibility_profile': result.get('compatibility_profile'),
                'response_time_ms': result.get('response_time_ms'),
                'failure_code': result.get('failure_code'),
                'draft_update': True,
            },
            queue_feedback=False,
        )
    return render_template(
        'integrations/observability/metrics_source/partials/_connection_test_result.html',
        connection_feedback=feedback,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@metrics_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def edit_instance(instance_id: int) -> ResponseReturnValue:
    return edit_instance_response(instance_id)


@metrics_bp.get('/instances/<int:instance_id>')
@permission_required('integrations.manage')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    history_trigger = request.args.get('history_trigger', '', type=str)
    history_health = request.args.get('history_health', '', type=str)
    history_readiness = request.args.get('history_readiness', '', type=str)
    binding_page = request.args.get('binding_page', 1, type=int) or 1
    binding_per_page = request.args.get('binding_per_page', 5, type=int) or 5
    context = _instance_detail_context(
        instance,
        page=page,
        per_page=per_page,
        history_trigger=history_trigger,
        history_health=history_health,
        history_readiness=history_readiness,
        binding_page=binding_page,
        binding_per_page=binding_per_page,
    )
    return render_template('integrations/observability/metrics_source/instance_detail.html', **context)


@metrics_bp.get('/instances/<int:instance_id>/bindings/registry')
@permission_required('integrations.manage')
def instance_binding_registry(instance_id: int) -> ResponseReturnValue:
    return binding_web.instance_binding_registry(instance_id)


@metrics_bp.post('/instances/<int:instance_id>/bindings')
@permission_required('integrations.manage')
def add_instance_binding(instance_id: int) -> ResponseReturnValue:
    return binding_web.add_instance_binding(instance_id)


@metrics_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/selector')
@permission_required('integrations.manage')
def update_instance_binding_selector(instance_id: int, binding_id: int) -> ResponseReturnValue:
    return binding_web.update_instance_binding_selector(instance_id, binding_id)


@metrics_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/validate')
@permission_required('integrations.manage')
def validate_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    return binding_web.validate_instance_binding(instance_id, binding_id)


@metrics_bp.get('/instances/<int:instance_id>/bindings/<int:binding_id>/validate/status/<string:task_id>')
@permission_required('integrations.manage')
def binding_validation_status(instance_id: int, binding_id: int, task_id: str) -> ResponseReturnValue:
    return binding_web.binding_validation_status(instance_id, binding_id, task_id)


@metrics_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/delete')
@permission_required('integrations.manage')
def delete_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    return binding_web.delete_instance_binding(instance_id, binding_id)


@metrics_bp.post(
    '/instances/<int:instance_id>/delete',
    endpoint='delete_instance',
)
@permission_required('integrations.manage')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    instance_name = instance.name
    is_htmx = is_htmx_request()
    try:
        remove_metrics_source(instance)
    except DeletionBlocked as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_delete_rejected',
            status='warning',
            title='Metrics Source instance deletion blocked',
            message=f'{instance_name} still has active operational dependencies.',
            detail=str(exc),
            action_url=url_for('jobs.executions', search=instance_name),
            action_label='Review active jobs',
            action_icon='list-checks',
            metadata={
                'instance_id': instance_id,
                'instance_name': instance_name,
                'active_jobs': exc.guard.active_jobs,
            },
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial(
                'integrations/observability/metrics_source/partials/_detail_scope.html',
                instance,
                operation_feedback=feedback,
            )
        return redirect(url_for('metrics.instance_detail', instance_id=instance_id) + '#scope')
    except ValueError as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_delete_rejected',
            status='error',
            title='Metrics Source instance not deleted',
            message=f'{instance_name} still has scope bindings.',
            detail=str(exc),
            action_url=url_for('metrics.instance_detail', instance_id=instance_id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='waypoints',
            metadata={'instance_id': instance_id, 'instance_name': instance_name},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial(
                'integrations/observability/metrics_source/partials/_detail_scope.html',
                instance,
                operation_feedback=feedback,
            )
        return redirect(url_for('metrics.instance_detail', instance_id=instance_id) + '#scope')
    except Exception as exc:
        logger.exception('Metrics Source instance deletion failed for %s.', instance_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_delete_failed',
            status='error',
            title='Metrics Source instance not deleted',
            message=f'KAORI could not delete {instance_name}.',
            detail='Review KAORI logs and database connectivity before retrying the deletion.',
            action_url=url_for('metrics.instance_detail', instance_id=instance_id) + '#scope',
            action_label='Review Metrics Source scope',
            action_icon='waypoints',
            metadata={'instance_id': instance_id, 'instance_name': instance_name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial(
                'integrations/observability/metrics_source/partials/_detail_scope.html',
                instance,
                operation_feedback=feedback,
            )
        return redirect(url_for('metrics.instance_detail', instance_id=instance_id) + '#scope')

    record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_deleted',
        status='success',
        title='Metrics Source instance deleted',
        message=f'{instance_name} was removed from the integration registry.',
        detail='Historical runtime observations and Activity Audit records remain available.',
        action_url=url_for('integrations.metrics_sources'),
        action_label='Open Metrics Sources',
        action_icon='activity',
        metadata={'instance_id': instance_id, 'instance_name': instance_name},
        queue_feedback=True,
    )
    location = url_for('integrations.metrics_sources')
    return _htmx_redirect(location) if is_htmx else redirect(location)


@metrics_bp.post('/instances/<int:instance_id>/test')
@permission_required('integrations.manage')
def instance_test(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    source_label = provider_definition(instance.provider_key).label
    is_htmx = is_htmx_request()
    try:
        result = test_and_persist_metrics_source(instance)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_connection_test',
            status='success',
            title=f'{source_label} connection verified',
            message=f'KAORI connected to {instance.name}.',
            detail=f'{(result.get("endpoint_product") or "endpoint").title()} {result.get("endpoint_version", "unknown")} responded successfully.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#validation',
            action_label=f'Review {source_label} validation',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'endpoint': instance.endpoint},
            queue_feedback=not is_htmx,
        )
    except MetricsSourceError as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_connection_test_failed',
            status='error',
            title=f'{source_label} connection failed',
            message=f'KAORI could not connect to {instance.name}.',
            detail=str(exc),
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#validation',
            action_label=f'Review {source_label} validation',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name},
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        rollback_metrics_source_transaction()
        logger.exception('Metrics Source connection test failed unexpectedly for %s.', instance_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_connection_test_failed',
            status='error',
            title=f'{source_label} connection test failed',
            message=f'KAORI could not complete the connection test for {instance.name}.',
            detail='Review endpoint access, credentials, TLS settings, and KAORI logs before retrying.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#validation',
            action_label=f'Review {source_label} validation',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_detail_validation_content.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#validation')


@metrics_bp.get('/instances/<int:instance_id>/validation/capabilities')
@permission_required('integrations.manage')
def instance_capability_registry(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    context = _instance_detail_context(instance)
    context['capability_registry'] = build_capability_registry_view(
        context.get('capability_rows', []),
        query=request.args.get('query', ''),
        requirement=request.args.get('requirement', 'all'),
        status=request.args.get('status', 'all'),
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 5),
        search_fields=('label', 'category', 'scope_label', 'source_owner', 'description'),
    )
    return render_template('integrations/observability/metrics_source/partials/_capability_registry.html', **context)


@metrics_bp.post('/instances/<int:instance_id>/validate')
@permission_required('integrations.manage')
def instance_validate(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    try:
        validation_job, created = enqueue_instance_validation(
            integration_type='metrics_source',
            integration_instance_id=instance.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='metrics_source_full_validation_queued'
            if created
            else 'metrics_source_full_validation_already_running',
            status='info' if created else 'warning',
            title='Metrics Source validation queued' if created else 'Metrics Source validation already running',
            message=(
                f'KAORI queued Full Validation for {instance.name}.'
                if created
                else f'Full Validation is already running for {instance.name}.'
            ),
            detail=(
                'The dedicated validation worker will rebuild capability, query-contract, retention, and module-readiness evidence.'
                if created
                else 'KAORI kept the existing task and did not enqueue a duplicate validation job.'
            ),
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Metrics Source validation',
            action_icon='scan-search',
            metadata={
                'task_id': validation_job.get('task_id'),
                'instance_id': instance.id,
                'instance_name': instance.name,
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Metrics Source Full Validation for %s.', instance_id)
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='metrics_source_full_validation_enqueue_failed',
            status='error',
            title='Metrics Source validation not queued',
            message=f'KAORI could not queue Full Validation for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Metrics Source validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_detail_validation_content.html',
            instance,
            operation_feedback=feedback,
            validation_job=validation_job,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#validation')


@metrics_bp.get('/instances/<int:instance_id>/validate/status/<string:task_id>')
@permission_required('integrations.manage')
def instance_validation_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='metrics_source',
        integration_instance_id=instance.integration_instance_id,
    ):
        abort(404)
    return _render_instance_partial(
        'integrations/observability/metrics_source/partials/_detail_validation_content.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        validation_job=snapshot,
    )


@metrics_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('integrations.manage')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    try:
        runtime_refresh_job, created = enqueue_runtime_health_refresh(
            integration_type='metrics_source',
            integration_instance_id=instance.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='metrics_source_runtime_refresh_queued'
            if created
            else 'metrics_source_runtime_refresh_already_running',
            status='info' if created else 'warning',
            title='Metrics Source runtime refresh queued'
            if created
            else 'Metrics Source runtime refresh already running',
            message=(
                f'KAORI queued a lightweight runtime refresh for {instance.name}.'
                if created
                else f'A runtime refresh is already running for {instance.name}.'
            ),
            detail=(
                'The runtime worker will check endpoint health without discarding Full Validation evidence.'
                if created
                else 'KAORI kept the active task and did not enqueue a duplicate.'
            ),
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#runtime',
            action_label='Review Metrics Source runtime',
            action_icon='activity',
            metadata={
                'task_id': runtime_refresh_job.get('task_id'),
                'instance_id': instance.id,
                'queue': current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Metrics Source runtime refresh for %s.', instance_id)
        runtime_refresh_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='metrics_source_runtime_refresh_enqueue_failed',
            status='error',
            title='Metrics Source runtime refresh not queued',
            message=f'KAORI could not queue runtime health refresh for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-runtime worker before retrying.',
            action_url=url_for('metrics.instance_detail', instance_id=instance.id) + '#runtime',
            action_label='Review Metrics Source runtime',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'integrations/observability/metrics_source/partials/_runtime_refresh_response.html',
            instance,
            operation_feedback=feedback,
            runtime_refresh_job=runtime_refresh_job,
        )
    return redirect(url_for('metrics.instance_detail', instance_id=instance.id) + '#runtime')


@metrics_bp.get('/instances/<int:instance_id>/runtime/refresh/status/<string:task_id>')
@permission_required('integrations.manage')
def runtime_refresh_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='metrics_source',
        integration_instance_id=instance.integration_instance_id,
    ):
        abort(404)
    return _render_instance_partial(
        'integrations/observability/metrics_source/partials/_runtime_refresh_response.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        runtime_refresh_job=snapshot,
    )


@metrics_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('integrations.manage')
def instance_runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    history_trigger = request.args.get('history_trigger', '', type=str)
    history_health = request.args.get('history_health', '', type=str)
    history_readiness = request.args.get('history_readiness', '', type=str)
    rows, pagination = paginate_runtime_history(
        'metrics_source',
        str(instance.id),
        page=page,
        per_page=per_page,
        trigger_type=history_trigger,
        health_status=history_health,
        readiness=history_readiness,
    )
    runtime_history = runtime_history_view(rows, pagination=pagination)
    return render_template(
        'integrations/observability/metrics_source/partials/_runtime_history.html',
        instance=instance,
        runtime_history=runtime_history,
    )
