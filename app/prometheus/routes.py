from __future__ import annotations

import json
import logging

from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.cluster.service import get_cluster_by_id
from app.common.http import is_htmx_request
from app.extensions.db import db
from app.integrations.deletion import DeletionBlocked
from app.integrations.lifecycle import ensure_canonical_instance
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    enqueue_binding_validation,
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
)
from app.models import PrometheusInstance
from app.models.integration import IntegrationBinding
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.prometheus.forms import PrometheusInstanceForm
from app.prometheus.presentation import build_instance_context
from app.prometheus.registration import issue_registration_proof, verify_registration_proof
from app.prometheus.repository import get_instance
from app.prometheus.service import (
    PrometheusService,
    create_prometheus_binding,
    remove_prometheus_instance,
    save_prometheus_instance,
    test_prometheus_form_connection,
    update_prometheus_binding_selector,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)


prometheus_bp = Blueprint(
    'prometheus',
    __name__,
    url_prefix='/integrations/prometheus',
)


def _instance_or_404(instance_id: int) -> PrometheusInstance:
    instance = get_instance(instance_id)
    if instance is None:
        abort(404)
    return instance


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response


def _render_instance_partial(
    template_name: str,
    instance: PrometheusInstance,
    *,
    operation_feedback: dict | None = None,
    **extra_context,
) -> str:
    context = _instance_detail_context(instance)
    context.update(extra_context)
    context['operation_feedback'] = operation_feedback
    context['notification_context'] = get_navigation_notification_context(
        user_id=int(current_user.id),
    )
    return render_template(template_name, **context)


def _instance_detail_context(
    instance: PrometheusInstance,
    *,
    page: int = 1,
    per_page: int = 5,
) -> dict:
    """Build the complete Prometheus manage-workspace context.

    All full-page and HTMX partial responses use the same context builder so
    Configuration, Validation, Runtime, Scope, and lifecycle controls cannot
    drift or render with missing route dependencies.
    """
    context = build_instance_context(instance, page=page, per_page=per_page)
    context['delete_instance_url'] = url_for(
        'prometheus.delete_instance',
        instance_id=instance.id,
    )
    validation_task_id = get_active_validation_task_id(
        provider_type='prometheus',
        operation='full_validation',
        instance_id=instance.id,
    )
    context['validation_job'] = build_validation_snapshot(validation_task_id) if validation_task_id else None
    runtime_task_id = get_active_validation_task_id(
        provider_type='prometheus',
        operation='runtime_refresh',
        instance_id=instance.id,
    )
    context['runtime_refresh_job'] = build_validation_snapshot(runtime_task_id) if runtime_task_id else None
    binding_job = None
    for binding in context.get('bindings', []):
        task_id = get_active_validation_task_id(
            provider_type='prometheus',
            operation='binding_validation',
            instance_id=instance.id,
            binding_id=binding.id,
        )
        if task_id:
            binding_job = build_validation_snapshot(task_id)
            break
    context['binding_validation_job'] = binding_job
    return context


@prometheus_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def new_instance() -> ResponseReturnValue:
    cluster_id = request.values.get('cluster_id', '').strip()
    initial_cluster = get_cluster_by_id(cluster_id) if cluster_id else None
    form = PrometheusInstanceForm()
    operation_feedback = None
    registration_proof = None
    is_htmx = is_htmx_request()

    if request.method == 'GET':
        form.enabled.data = True
        form.verify_ssl.data = True

    if request.method == 'POST':
        if form.validate_on_submit():
            submitted_proof = str(request.form.get('connection_test_proof') or '').strip()
            proof_valid, proof_error = verify_registration_proof(
                token=submitted_proof,
                form=form,
                user_id=int(current_user.id),
            )
            if not proof_valid:
                operation_feedback = record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_create_rejected',
                    status='error',
                    title='Connection test required',
                    message='Run Test Connection successfully before registering the Prometheus connection.',
                    detail=proof_error,
                    action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                    action_label='Review Prometheus form',
                    action_icon='chart-spline',
                    metadata={
                        'cluster_id': cluster_id or None,
                        'submitted_name': (form.name.data or '').strip() or 'Draft Prometheus connection',
                        'registration_stage': 'connection_test_proof',
                    },
                    queue_feedback=not is_htmx,
                )
            else:
                connection_test = test_prometheus_form_connection(form)
                if not connection_test.get('connected'):
                    operation_feedback = record_operational_activity(
                        user_id=current_user.id,
                        event_type='prometheus_instance_create_rejected',
                        status='error',
                        title='Prometheus connection not registered',
                        message='The connection changed or became unavailable before registration completed.',
                        detail=(
                            connection_test.get('error')
                            or connection_test.get('reason')
                            or 'Review endpoint, authentication, TLS, and compatibility settings.'
                        ),
                        action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                        action_label='Review Prometheus form',
                        action_icon='chart-spline',
                        metadata={
                            'cluster_id': cluster_id or None,
                            'failure_code': connection_test.get('failure_code'),
                            'endpoint_host': connection_test.get('endpoint_host'),
                            'request_path': connection_test.get('request_path'),
                            'submitted_name': (form.name.data or '').strip() or 'Draft Prometheus connection',
                            'registration_stage': 'pre_save_recheck',
                        },
                        queue_feedback=not is_htmx,
                    )
                else:
                    try:
                        instance = save_prometheus_instance(form, initial_cluster=initial_cluster)
                    except PrometheusError as exc:
                        operation_feedback = record_operational_activity(
                            user_id=current_user.id,
                            event_type='prometheus_instance_create_rejected',
                            status='error',
                            title='Prometheus connection not registered',
                            message='KAORI could not create the Prometheus connection.',
                            detail=str(exc),
                            action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                            action_label='Review Prometheus form',
                            action_icon='chart-spline',
                            metadata={
                                'cluster_id': cluster_id or None,
                                'submitted_name': (form.name.data or '').strip() or 'Draft Prometheus connection',
                                'registration_stage': 'persistence_validation',
                            },
                            queue_feedback=not is_htmx,
                        )
                    except Exception as exc:
                        logger.exception('Prometheus instance creation failed.')
                        operation_feedback = record_operational_activity(
                            user_id=current_user.id,
                            event_type='prometheus_instance_create_failed',
                            status='error',
                            title='Prometheus connection not registered',
                            message='KAORI could not save the Prometheus connection.',
                            detail='Review KAORI logs and database connectivity before retrying.',
                            action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                            action_label='Review Prometheus form',
                            action_icon='chart-spline',
                            metadata={
                                'cluster_id': cluster_id or None,
                                'reason': type(exc).__name__,
                                'submitted_name': (form.name.data or '').strip() or 'Draft Prometheus connection',
                                'registration_stage': 'database_commit',
                            },
                            queue_feedback=not is_htmx,
                        )
                    else:
                        record_operational_activity(
                            user_id=current_user.id,
                            event_type='prometheus_instance_created',
                            status='success',
                            title='Prometheus connection registered',
                            message=f'{instance.name} is now registered as a reusable Prometheus source.',
                            detail='Reachability and compatibility passed during registration. Run Full Validation, review readiness, then create scope bindings before operational use.',
                            action_url=url_for('prometheus.instance_detail', instance_id=instance.id),
                            action_label='Open Prometheus integration',
                            action_icon='chart-spline',
                            metadata={
                                'instance_id': instance.id,
                                'cluster_id': cluster_id or None,
                                'connection_response_time_ms': connection_test.get('response_time_ms'),
                                'detected_version': connection_test.get('version'),
                                'endpoint_product': connection_test.get('endpoint_product'),
                            },
                            queue_feedback=True,
                        )
                        location = url_for('prometheus.instance_detail', instance_id=instance.id)
                        return _htmx_redirect(location) if is_htmx else redirect(location)
        else:
            operation_feedback = record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_create_rejected',
                status='error',
                title='Prometheus connection not registered',
                message='Review the highlighted connection fields before testing or registering this source.',
                detail='The submitted form did not satisfy the Prometheus connection contract.',
                action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                action_label='Review Prometheus form',
                action_icon='chart-spline',
                metadata={
                    'cluster_id': cluster_id or None,
                    'fields': sorted(form.errors),
                    'registration_stage': 'form_validation',
                },
                queue_feedback=not is_htmx,
            )

    return render_template(
        'prometheus/instance_form.html',
        form=form,
        instance=None,
        initial_cluster=initial_cluster,
        registration_proof=registration_proof,
        operation_feedback=operation_feedback,
        notification_context=(
            get_navigation_notification_context(user_id=int(current_user.id))
            if operation_feedback is not None
            else None
        ),
    )


@prometheus_bp.post('/instances/test-connection')
@permission_required('settings.manage_integrations')
def test_new_instance_connection() -> ResponseReturnValue:
    form = PrometheusInstanceForm()
    cluster_id = request.form.get('cluster_id', '').strip()

    if not form.validate_on_submit():
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test_failed',
            status='error',
            title='Prometheus connection test failed',
            message='Review the highlighted connection fields before testing this source.',
            detail='The submitted form did not satisfy the Prometheus connection contract.',
            action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
            action_label='Review Prometheus form',
            action_icon='chart-spline',
            metadata={
                'cluster_id': cluster_id or None,
                'fields': sorted(form.errors),
                'draft_connection': True,
                'registration_stage': 'connection_test_form_validation',
            },
            queue_feedback=False,
        )
        result = {'connected': False}
    else:
        result = test_prometheus_form_connection(form)
        if result.get('connected'):
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_connection_test',
                status='success',
                title='Prometheus connection verified',
                message='KAORI reached the submitted Prometheus-compatible endpoint.',
                detail=(
                    f'{str(result.get("endpoint_product") or "Prometheus").title()} '
                    f'{result.get("version") or "unknown"} responded in '
                    f'{result.get("response_time_ms") or 0} ms. Register the connection, then run Full Validation.'
                ),
                action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                action_label='Review Prometheus form',
                action_icon='chart-spline',
                metadata={
                    'cluster_id': cluster_id or None,
                    'endpoint_host': result.get('endpoint_host'),
                    'endpoint_product': result.get('endpoint_product'),
                    'version': result.get('version'),
                    'compatibility_profile': result.get('compatibility_profile'),
                    'response_time_ms': result.get('response_time_ms'),
                    'request_path': result.get('request_path'),
                    'draft_connection': True,
                    'submitted_name': (form.name.data or '').strip() or 'Draft Prometheus connection',
                },
                queue_feedback=False,
            )
        else:
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_connection_test_failed',
                status='error',
                title='Prometheus connection test failed',
                message='KAORI could not verify the submitted Prometheus-compatible endpoint.',
                detail=(
                    result.get('error')
                    or result.get('reason')
                    or 'Review endpoint, authentication, TLS, compatibility, and network reachability.'
                ),
                action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                action_label='Review Prometheus form',
                action_icon='chart-spline',
                metadata={
                    'cluster_id': cluster_id or None,
                    'failure_code': result.get('failure_code'),
                    'endpoint_host': result.get('endpoint_host'),
                    'endpoint_port': result.get('endpoint_port'),
                    'request_path': result.get('request_path'),
                    'draft_connection': True,
                    'submitted_name': (form.name.data or '').strip() or 'Draft Prometheus connection',
                },
                queue_feedback=False,
            )

    registration_proof = (
        issue_registration_proof(form=form, user_id=int(current_user.id)) if result.get('connected') else ''
    )
    response = make_response(
        render_template(
            'prometheus/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {
            'prometheus-connection-tested': {
                'connected': bool(result.get('connected')),
                'proof': registration_proof,
            }
        },
        separators=(',', ':'),
    )
    return response


@prometheus_bp.post('/instances/<int:instance_id>/test-configuration')
@permission_required('settings.manage_integrations')
def test_instance_configuration(instance_id: int) -> ResponseReturnValue:
    """Test submitted edit settings without persisting them."""
    instance = _instance_or_404(instance_id)
    form = PrometheusInstanceForm()
    setattr(form, '_existing_instance', instance)
    if not form.validate_on_submit():
        result = {'connected': False}
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test_failed',
            status='error',
            title='Prometheus configuration test failed',
            message=f'Review the submitted settings for {instance.name}.',
            detail='The edited connection form did not satisfy the Prometheus connection contract.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
            action_label='Review Prometheus configuration',
            action_icon='settings-2',
            metadata={
                'instance_id': instance.id,
                'fields': sorted(form.errors),
                'draft_update': True,
            },
            queue_feedback=False,
        )
    else:
        result = test_prometheus_form_connection(form, existing_instance=instance)
        connected = bool(result.get('connected'))
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test' if connected else 'prometheus_connection_test_failed',
            status='success' if connected else 'error',
            title='Prometheus configuration verified' if connected else 'Prometheus configuration test failed',
            message=(
                f'KAORI reached the submitted settings for {instance.name}.'
                if connected
                else f'KAORI could not verify the submitted settings for {instance.name}.'
            ),
            detail=(
                f'{str(result.get("endpoint_product") or "Prometheus").title()} '
                f'{result.get("version") or "unknown"} responded in {result.get("response_time_ms") or 0} ms. '
                'Save the configuration, then run Full Validation.'
                if connected
                else result.get('error')
                or result.get('reason')
                or 'Review endpoint, authentication, TLS, and network reachability.'
            ),
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
            action_label='Review Prometheus configuration',
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
        'prometheus/partials/_connection_test_result.html',
        connection_feedback=feedback,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@prometheus_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = PrometheusInstanceForm(obj=instance)
    setattr(form, '_existing_instance', instance)
    operation_feedback = None
    is_htmx = is_htmx_request()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                instance = save_prometheus_instance(form, instance=instance)
            except Exception as exc:
                logger.exception('Prometheus instance update failed for %s.', instance_id)
                operation_feedback = record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_update_failed',
                    status='error',
                    title='Prometheus instance not updated',
                    message=f'KAORI could not update {instance.name}.',
                    detail='Review the submitted connection settings and KAORI logs before retrying.',
                    action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
                    action_label='Review Prometheus configuration',
                    action_icon='settings-2',
                    metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
                    queue_feedback=not is_htmx,
                )
            else:
                operation_feedback = record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_updated',
                    status='success',
                    title='Prometheus instance updated',
                    message=f'{instance.name} connection settings were saved.',
                    detail='Readiness returned to Validation Required until Full Validation rebuilds the technical evidence.',
                    action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
                    action_label='Review Prometheus validation',
                    action_icon='scan-search',
                    metadata={'instance_id': instance.id},
                    queue_feedback=not is_htmx,
                )
        else:
            operation_feedback = record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_update_rejected',
                status='error',
                title='Prometheus instance not updated',
                message=f'KAORI could not update {instance.name}.',
                detail='Review the highlighted configuration fields before saving again.',
                action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
                action_label='Review Prometheus configuration',
                action_icon='settings-2',
                metadata={'instance_id': instance.id, 'fields': sorted(form.errors)},
                queue_feedback=not is_htmx,
            )

        if is_htmx:
            return _render_instance_partial(
                'prometheus/partials/_detail_configuration.html',
                instance,
                operation_feedback=operation_feedback,
                form=form,
            )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    context = _instance_detail_context(instance, page=page, per_page=per_page)
    context['form'] = form
    return render_template('prometheus/instance_detail.html', **context)


@prometheus_bp.post('/instances/<int:instance_id>/bindings')
@permission_required('settings.manage_integrations')
def add_instance_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    cluster_id = request.form.get('cluster_id', '').strip()
    cluster = get_cluster_by_id(cluster_id) if cluster_id else None
    role = (request.form.get('binding_role') or 'primary').strip().lower()
    priority = request.form.get('priority', 100, type=int) or 100
    selector_label = request.form.get('selector_label', '').strip() or None
    selector_value = request.form.get('selector_value', '').strip() or None
    selector_operator = request.form.get('selector_operator', '=').strip() or '='
    is_htmx = is_htmx_request()

    try:
        if cluster is None:
            raise ValueError('Select an available managed cluster.')
        binding = create_prometheus_binding(
            instance=instance,
            cluster=cluster,
            role=role,
            priority=priority,
            selector_label=selector_label,
            selector_value=selector_value,
            selector_operator=selector_operator,
        )
    except ValueError as exc:
        error = str(exc)
        operation_feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_create_rejected',
            status='error',
            title='Prometheus binding not saved',
            message=f'KAORI could not bind {instance.name} to {cluster.name if cluster else "the selected scope"}.',
            detail=error,
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={
                'instance_id': instance.id,
                'cluster_id': cluster.id if cluster else cluster_id or None,
                'binding_role': role,
                'priority': priority,
                'selector_label': selector_label,
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception('Prometheus binding creation failed for instance %s.', instance_id)
        error = 'KAORI could not save the scope binding. Review database connectivity and retry.'
        operation_feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_create_failed',
            status='error',
            title='Prometheus binding not saved',
            message=f'KAORI could not bind {instance.name} to {cluster.name if cluster else "the selected scope"}.',
            detail=error,
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={
                'instance_id': instance.id,
                'cluster_id': cluster.id if cluster else cluster_id or None,
                'reason': type(exc).__name__,
            },
            queue_feedback=not is_htmx,
        )
    else:
        error = None
        operation_feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_created',
            status='success',
            title='Prometheus binding created',
            message=f'{instance.name} is now available to {cluster.name}.',
            detail=f'{role.title()} source with priority {priority}. Metrics identity: {selector_label or "unscoped"}.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={
                'instance_id': instance.id,
                'binding_id': binding.id,
                'cluster_id': cluster.id,
                'selector_label': selector_label,
                'selector_value': selector_value,
            },
            queue_feedback=not is_htmx,
        )

    if is_htmx:
        return _render_instance_partial(
            'prometheus/partials/_detail_scope.html',
            instance,
            operation_feedback=operation_feedback,
            binding_error=error,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope')


@prometheus_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/selector')
@permission_required('settings.manage_integrations')
def update_instance_binding_selector(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = db.session.get(IntegrationBinding, binding_id)
    if binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    is_htmx = is_htmx_request()
    selector_label = request.form.get('selector_label', '').strip() or None
    selector_value = request.form.get('selector_value', '').strip() or None
    selector_operator = request.form.get('selector_operator', '=').strip() or '='
    try:
        update_prometheus_binding_selector(
            instance=instance,
            binding=binding,
            selector_label=selector_label,
            selector_value=selector_value,
            selector_operator=selector_operator,
        )
    except ValueError as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_selector_update_rejected',
            status='error',
            title='Metrics identity not updated',
            message='KAORI could not save the Prometheus binding selector.',
            detail=str(exc),
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='scan-line',
            metadata={'instance_id': instance.id, 'binding_id': binding.id},
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception('Prometheus binding selector update failed for binding %s.', binding_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_selector_update_failed',
            status='error',
            title='Metrics identity not updated',
            message='KAORI could not persist the Prometheus binding selector.',
            detail='Review KAORI logs and database connectivity before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='scan-line',
            metadata={'instance_id': instance.id, 'binding_id': binding.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_selector_updated',
            status='success',
            title='Metrics identity updated',
            message='The Prometheus binding selector was saved.',
            detail='Binding readiness returned to Validation Required. Validate the binding before operational use.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
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
            'prometheus/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope')


@prometheus_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/validate')
@permission_required('settings.manage_integrations')
def validate_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = db.session.get(IntegrationBinding, binding_id)
    if binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    is_htmx = is_htmx_request()
    try:
        validation_job, created = enqueue_binding_validation(
            provider_type='prometheus',
            instance_id=instance.id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='prometheus_binding_validation_queued'
            if created
            else 'prometheus_binding_validation_already_running',
            status='info' if created else 'warning',
            title='Prometheus binding validation queued'
            if created
            else 'Prometheus binding validation already running',
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
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
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
        logger.exception('Could not enqueue Prometheus binding validation for %s.', binding_id)
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='prometheus_binding_validation_enqueue_failed',
            status='error',
            title='Prometheus binding validation not queued',
            message='KAORI could not queue the metrics identity validation.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'binding_id': binding.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'prometheus/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
            binding_validation_job=validation_job,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope')


@prometheus_bp.get('/instances/<int:instance_id>/bindings/<int:binding_id>/validate/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def binding_validation_status(instance_id: int, binding_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = db.session.get(IntegrationBinding, binding_id)
    if binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='prometheus',
        instance_id=instance.id,
        binding_id=binding.id,
    ):
        abort(404)
    return _render_instance_partial(
        'prometheus/partials/_detail_scope.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        binding_validation_job=snapshot,
    )


@prometheus_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/delete')
@permission_required('settings.manage_integrations')
def delete_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    binding = IntegrationBinding.query.filter_by(
        id=binding_id,
        integration_instance_id=instance.integration_instance_id,
    ).first()
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
        db.session.delete(binding)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception('Prometheus binding deletion failed for binding %s.', binding_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_delete_failed',
            status='error',
            title='Prometheus binding not removed',
            message=f'KAORI could not remove the selected binding from {instance.name}.',
            detail='Review KAORI logs and database connectivity before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={**binding_metadata, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_deleted',
            status='success',
            title='Prometheus binding removed',
            message=f'{instance.name} is no longer mapped to the selected managed cluster.',
            detail=f'{binding.asset_type}:{binding.asset_key} was removed.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata=binding_metadata,
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'prometheus/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope')


@prometheus_bp.post(
    '/instances/<int:instance_id>/delete',
    endpoint='delete_instance',
)
@permission_required('settings.manage_integrations')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    instance_name = instance.name
    is_htmx = is_htmx_request()
    try:
        remove_prometheus_instance(instance)
    except DeletionBlocked as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_delete_rejected',
            status='warning',
            title='Prometheus instance deletion blocked',
            message=f'{instance_name} still has active operational dependencies.',
            detail=str(exc),
            action_url=url_for('integrations.jobs', search=instance_name),
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
                'prometheus/partials/_detail_scope.html', instance, operation_feedback=feedback
            )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope')
    except ValueError as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_delete_rejected',
            status='error',
            title='Prometheus instance not deleted',
            message=f'{instance_name} still has scope bindings.',
            detail=str(exc),
            action_url=url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={'instance_id': instance_id, 'instance_name': instance_name},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial(
                'prometheus/partials/_detail_scope.html', instance, operation_feedback=feedback
            )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope')
    except Exception as exc:
        logger.exception('Prometheus instance deletion failed for %s.', instance_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_delete_failed',
            status='error',
            title='Prometheus instance not deleted',
            message=f'KAORI could not delete {instance_name}.',
            detail='Review KAORI logs and database connectivity before retrying the deletion.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={'instance_id': instance_id, 'instance_name': instance_name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial(
                'prometheus/partials/_detail_scope.html', instance, operation_feedback=feedback
            )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope')

    record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_instance_deleted',
        status='success',
        title='Prometheus instance deleted',
        message=f'{instance_name} was removed from the integration registry.',
        detail='Historical runtime observations and Activity Audit records remain available.',
        action_url=url_for('integrations.prometheus'),
        action_label='Open Prometheus integrations',
        action_icon='activity',
        metadata={'instance_id': instance_id, 'instance_name': instance_name},
        queue_feedback=True,
    )
    location = url_for('integrations.prometheus')
    return _htmx_redirect(location) if is_htmx else redirect(location)


@prometheus_bp.post('/instances/<int:instance_id>/test')
@permission_required('settings.manage_integrations')
def instance_test(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    try:
        result = PrometheusService(instance).test_connection()
        ensure_canonical_instance(instance, provider_type='prometheus')
        db.session.commit()
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test',
            status='success',
            title='Prometheus connection verified',
            message=f'KAORI connected to {instance.name}.',
            detail=f'{(result.get("endpoint_product") or "endpoint").title()} {result.get("endpoint_version", "unknown")} responded successfully.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'endpoint': instance.endpoint},
            queue_feedback=not is_htmx,
        )
    except PrometheusError as exc:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test_failed',
            status='error',
            title='Prometheus connection failed',
            message=f'KAORI could not connect to {instance.name}.',
            detail=str(exc),
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name},
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception('Prometheus connection test failed unexpectedly for %s.', instance_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test_failed',
            status='error',
            title='Prometheus connection test failed',
            message=f'KAORI could not complete the connection test for {instance.name}.',
            detail='Review endpoint access, credentials, TLS settings, and KAORI logs before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'prometheus/partials/_detail_validation_content.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation')


@prometheus_bp.post('/instances/<int:instance_id>/validate')
@permission_required('settings.manage_integrations')
def instance_validate(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    try:
        validation_job, created = enqueue_instance_validation(
            provider_type='prometheus',
            instance_id=instance.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='prometheus_full_validation_queued' if created else 'prometheus_full_validation_already_running',
            status='info' if created else 'warning',
            title='Prometheus validation queued' if created else 'Prometheus validation already running',
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
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
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
        logger.exception('Could not enqueue Prometheus Full Validation for %s.', instance_id)
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='prometheus_full_validation_enqueue_failed',
            status='error',
            title='Prometheus validation not queued',
            message=f'KAORI could not queue Full Validation for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'prometheus/partials/_detail_validation_content.html',
            instance,
            operation_feedback=feedback,
            validation_job=validation_job,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation')


@prometheus_bp.get('/instances/<int:instance_id>/validate/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def instance_validation_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='prometheus',
        instance_id=instance.id,
    ):
        abort(404)
    return _render_instance_partial(
        'prometheus/partials/_detail_validation_content.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        validation_job=snapshot,
    )


@prometheus_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('settings.manage_integrations')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = is_htmx_request()
    try:
        runtime_refresh_job, created = enqueue_runtime_health_refresh(
            provider_type='prometheus',
            instance_id=instance.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='prometheus_runtime_refresh_queued' if created else 'prometheus_runtime_refresh_already_running',
            status='info' if created else 'warning',
            title='Prometheus runtime refresh queued' if created else 'Prometheus runtime refresh already running',
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
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#runtime',
            action_label='Review Prometheus runtime',
            action_icon='activity',
            metadata={
                'task_id': runtime_refresh_job.get('task_id'),
                'instance_id': instance.id,
                'queue': current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Prometheus runtime refresh for %s.', instance_id)
        runtime_refresh_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='prometheus_runtime_refresh_enqueue_failed',
            status='error',
            title='Prometheus runtime refresh not queued',
            message=f'KAORI could not queue runtime health refresh for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-runtime worker before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#runtime',
            action_label='Review Prometheus runtime',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'prometheus/partials/_runtime_refresh_response.html',
            instance,
            operation_feedback=feedback,
            runtime_refresh_job=runtime_refresh_job,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#runtime')


@prometheus_bp.get('/instances/<int:instance_id>/runtime/refresh/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def runtime_refresh_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='prometheus',
        instance_id=instance.id,
    ):
        abort(404)
    return _render_instance_partial(
        'prometheus/partials/_runtime_refresh_response.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        runtime_refresh_job=snapshot,
    )


@prometheus_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('settings.manage_integrations')
def instance_runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    rows, pagination = paginate_runtime_history(
        'prometheus',
        str(instance.id),
        page=page,
        per_page=per_page,
    )
    return render_template(
        'prometheus/partials/_runtime_history.html',
        instance=instance,
        runtime_history=runtime_history_view(rows, pagination=pagination),
    )
