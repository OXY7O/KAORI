from __future__ import annotations

import json
import logging
from dataclasses import replace

from flask import Blueprint, abort, jsonify, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.alertmanager.forms import (
    AlertmanagerBindingForm,
    parse_alertmanager_binding_form,
    parse_alertmanager_instance_form,
)
from app.alertmanager.notifications import record_instance_activity
from app.alertmanager.presentation import build_instance_context, build_runtime_history_context
from app.alertmanager.registration import issue_registration_proof, verify_registration_proof
from app.alertmanager.runtime_adapter import runtime_adapter
from app.alertmanager.service import (
    add_alertmanager_binding,
    create_alertmanager_instance,
    get_alertmanager_binding,
    get_alertmanager_instance,
    get_cluster_by_id,
    materialize_legacy_cluster_config,
    remove_alertmanager_binding,
    remove_alertmanager_instance,
    save_alertmanager_instance,
    test_alertmanager_connection,
    test_alertmanager_form_connection,
    update_alertmanager_binding_selector,
    validate_alertmanager_instance,
    validate_alertmanager_binding,
)
from app.integrations.runtime.monitoring import refresh_and_record as refresh_provider_runtime
from app.integrations.runtime.presentation import runtime_state_view
from app.notifications.service import get_navigation_notification_context
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

alertmanager_bp = Blueprint(
    'alertmanager',
    __name__,
    url_prefix='/integrations/alertmanager',
)


def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request') == 'true'


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response


def _render_instance_partial(
    template_name: str,
    instance,
    *,
    operation_feedback: dict | None = None,
    **extra_context,
) -> str:
    context = build_instance_context(instance)
    context.update(extra_context)
    context['operation_feedback'] = operation_feedback
    context['notification_context'] = get_navigation_notification_context(
        user_id=int(current_user.id),
    )
    return render_template(template_name, **context)


@alertmanager_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def new_instance() -> ResponseReturnValue:
    initial_cluster_id = request.values.get('cluster_id', '').strip()
    initial_cluster = get_cluster_by_id(initial_cluster_id) if initial_cluster_id else None
    draft_form = None
    registration_proof = None
    operation_feedback = None
    is_htmx = _is_htmx_request()

    if request.method == 'POST':
        form = parse_alertmanager_instance_form(request.form)
        if not form.name and initial_cluster is not None:
            form = replace(form, name=f'{initial_cluster.name} Alertmanager', deployment_type='cluster_managed')
        draft_form = form

        submitted_proof = str(request.form.get('connection_test_proof') or '').strip()
        proof_valid, proof_error = verify_registration_proof(
            token=submitted_proof,
            form=form,
            user_id=int(current_user.id),
        )
        if not proof_valid:
            operation_feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=None,
                event_type='alertmanager_instance_create_rejected',
                status='error',
                title='Connection test required',
                message='Run Test Connection successfully before registering the Alertmanager instance.',
                detail=proof_error,
                metadata={
                    'cluster_id': initial_cluster_id or None,
                    'submitted_name': form.name or 'Draft Alertmanager connection',
                    'registration_stage': 'connection_test_proof',
                },
                queue_feedback=not is_htmx,
            )
        else:
            connection_test = test_alertmanager_form_connection(form)
            if not connection_test.get('connected'):
                failure_detail = (
                    connection_test.get('error')
                    or connection_test.get('reason')
                    or 'Review endpoint, authentication, TLS, and network reachability.'
                )
                operation_feedback = record_instance_activity(
                    user_id=int(current_user.id),
                    instance=None,
                    event_type='alertmanager_instance_create_rejected',
                    status='error',
                    title='Alertmanager instance not created',
                    message='The connection changed or became unreachable before registration completed.',
                    detail=failure_detail,
                    metadata={
                        'cluster_id': initial_cluster_id or None,
                        'failure_code': connection_test.get('failure_code'),
                        'endpoint_host': connection_test.get('endpoint_host'),
                        'request_path': connection_test.get('request_path'),
                        'submitted_name': form.name or 'Draft Alertmanager connection',
                        'registration_stage': 'pre_save_recheck',
                    },
                    queue_feedback=not is_htmx,
                )
            else:
                try:
                    initial_binding = (
                        AlertmanagerBindingForm(
                            scope_type='kubernetes_cluster',
                            scope_key=initial_cluster.id,
                            binding_role='primary',
                            priority=100,
                            enabled=True,
                            selector_label='cluster',
                            selector_value=initial_cluster.name,
                            selector_operator='=',
                        )
                        if initial_cluster is not None
                        else None
                    )
                    instance = create_alertmanager_instance(form=form, initial_binding=initial_binding)
                except ValueError as exc:
                    operation_feedback = record_instance_activity(
                        user_id=int(current_user.id),
                        instance=None,
                        event_type='alertmanager_instance_create_rejected',
                        status='error',
                        title='Alertmanager instance not created',
                        message='KAORI could not create the Alertmanager instance.',
                        detail=str(exc),
                        metadata={
                            'cluster_id': initial_cluster_id or None,
                            'submitted_name': form.name or 'Draft Alertmanager connection',
                            'registration_stage': 'persistence_validation',
                        },
                        queue_feedback=not is_htmx,
                    )
                except Exception as exc:
                    logger.exception('Alertmanager instance creation failed.')
                    operation_feedback = record_instance_activity(
                        user_id=int(current_user.id),
                        instance=None,
                        event_type='alertmanager_instance_create_failed',
                        status='error',
                        title='Alertmanager instance not created',
                        message='KAORI could not save the Alertmanager instance.',
                        detail='Review KAORI logs and database connectivity before retrying.',
                        metadata={
                            'reason': type(exc).__name__,
                            'submitted_name': form.name or 'Draft Alertmanager connection',
                            'registration_stage': 'database_commit',
                        },
                        queue_feedback=not is_htmx,
                    )
                else:
                    record_instance_activity(
                        user_id=int(current_user.id),
                        instance=instance,
                        event_type='alertmanager_instance_created',
                        status='success',
                        title='Alertmanager instance created',
                        message=f'{instance.name} is now registered as an Alertmanager source.',
                        detail='Reachability passed during registration. Run Full Validation, review readiness, then create scope bindings before operational use.',
                        metadata={
                            'initial_cluster_id': initial_cluster_id or None,
                            'connection_response_time_ms': connection_test.get('response_time_ms'),
                            'detected_version': connection_test.get('version'),
                        },
                        queue_feedback=True,
                    )
                    location = url_for('alertmanager.instance_detail', instance_id=instance.id)
                    return _htmx_redirect(location) if is_htmx else redirect(location)

    return render_template(
        'alertmanager/instance_form.html',
        **build_instance_context(),
        initial_cluster=initial_cluster,
        draft_form=draft_form,
        registration_proof=registration_proof,
        operation_feedback=operation_feedback,
        notification_context=(
            get_navigation_notification_context(user_id=int(current_user.id))
            if operation_feedback is not None
            else None
        ),
    )

@alertmanager_bp.post('/instances/test-connection')
@permission_required('settings.manage_integrations')
def test_new_instance_connection() -> ResponseReturnValue:
    form = parse_alertmanager_instance_form(request.form)
    result = test_alertmanager_form_connection(form)

    if result.get('connected'):
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=None,
            event_type='alertmanager_connection_test',
            status='success',
            title='Alertmanager connection verified',
            message='KAORI reached the submitted Alertmanager endpoint.',
            detail=(
                f"Status API responded in {result.get('response_time_ms', 0)} ms. "
                'Register the instance, then run full validation from its detail page.'
            ),
            metadata={
                'endpoint_host': result.get('endpoint_host'),
                'version': result.get('version'),
                'response_time_ms': result.get('response_time_ms'),
                'request_path': result.get('request_path'),
                'draft_connection': True,
                'submitted_name': form.name or 'Draft Alertmanager connection',
            },
            queue_feedback=False,
        )
    else:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=None,
            event_type='alertmanager_connection_test_failed',
            status='error',
            title='Alertmanager connection test failed',
            message='KAORI could not reach the submitted Alertmanager endpoint.',
            detail=result.get('error') or 'Review endpoint, authentication, TLS, and network reachability.',
            metadata={
                'failure_code': result.get('failure_code'),
                'endpoint_host': result.get('endpoint_host'),
                'endpoint_port': result.get('endpoint_port'),
                'request_path': result.get('request_path'),
                'draft_connection': True,
                'submitted_name': form.name or 'Draft Alertmanager connection',
            },
            queue_feedback=False,
        )

    registration_proof = (
        issue_registration_proof(form=form, user_id=int(current_user.id))
        if result.get('connected')
        else ''
    )
    response = make_response(
        render_template(
            'alertmanager/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {
            'alertmanager-connection-tested': {
                'connected': bool(result.get('connected')),
                'proof': registration_proof,
            }
        },
        separators=(',', ':'),
    )
    return response


@alertmanager_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    is_htmx = _is_htmx_request()

    if request.method == 'POST':
        form = parse_alertmanager_instance_form(request.form)
        try:
            instance = save_alertmanager_instance(form=form, instance=instance)
        except ValueError as exc:
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_update_rejected',
                status='error',
                title='Alertmanager instance not updated',
                message=f'KAORI could not update {instance.name}.',
                detail=str(exc),
                queue_feedback=not is_htmx,
            )
        except Exception as exc:
            logger.exception('Alertmanager instance update failed for %s.', instance_id)
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_update_failed',
                status='error',
                title='Alertmanager instance not updated',
                message=f'KAORI could not update {instance.name}.',
                detail='Review KAORI logs and database connectivity before retrying.',
                metadata={'reason': type(exc).__name__},
                queue_feedback=not is_htmx,
            )
        else:
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_updated',
                status='success',
                title='Alertmanager instance updated',
                message=f'{instance.name} connection settings were saved.',
                detail='Readiness is now Validation Required until a Full Validation completes.',
                queue_feedback=not is_htmx,
            )
        if is_htmx:
            return _render_instance_partial(
                'alertmanager/partials/_detail_configuration.html',
                instance,
                operation_feedback=feedback,
            )
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#configuration')

    return render_template('alertmanager/instance_detail.html', **build_instance_context(instance))

@alertmanager_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('settings.manage_integrations')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)

    try:
        result, state, _observation = refresh_provider_runtime(
            runtime_adapter,
            instance,
            trigger_type='manual',
        )
    except Exception as exc:  # pragma: no cover - defensive runtime persistence boundary
        logger.exception('Alertmanager runtime refresh failed for %s.', instance_id)
        state = runtime_adapter.get_state(instance)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_runtime_refresh_failed',
            status='error',
            title='Alertmanager runtime refresh failed',
            message=f'KAORI could not refresh runtime health for {instance.name}.',
            detail='Review endpoint reachability, integration credentials, and runtime observation storage before retrying.',
            metadata={
                'reason': type(exc).__name__,
                'health_status': state.health.status,
                'readiness_status': state.readiness,
            },
            queue_feedback=False,
        )
    else:
        refresh_succeeded = bool(result.connected)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_runtime_refreshed' if refresh_succeeded else 'alertmanager_runtime_refresh_failed',
            status=(
                'success'
                if refresh_succeeded and state.health.status == 'healthy'
                else ('warning' if refresh_succeeded and state.health.status == 'degraded' else 'error')
            ),
            title='Alertmanager runtime refreshed' if refresh_succeeded else 'Alertmanager runtime refresh failed',
            message=(
                f'{instance.name} runtime health is {state.health.status}.'
                if refresh_succeeded
                else f'KAORI could not refresh runtime health for {instance.name}.'
            ),
            detail=result.reason or state.message,
            metadata={
                'health_status': state.health.status,
                'health_score': state.health.score,
                'readiness_status': state.readiness,
                'latency_ms': state.latency_ms,
                'capability_profile': state.snapshot.profile,
                'capability_count': len(state.snapshot.capabilities),
            },
            queue_feedback=False,
        )
    return _render_instance_partial(
        'alertmanager/partials/_runtime_refresh_response.html',
        instance,
        operation_feedback=feedback,
        runtime_state=runtime_state_view(state),
        runtime_history=build_runtime_history_context(instance),
    )


@alertmanager_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('settings.manage_integrations')
def runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    page = request.args.get('page', default=1, type=int) or 1
    per_page = request.args.get('per_page', default=5, type=int) or 5
    return render_template(
        'alertmanager/partials/_runtime_history.html',
        instance=instance,
        runtime_history=build_runtime_history_context(
            instance,
            page=page,
            per_page=per_page,
        ),
    )


@alertmanager_bp.post('/instances/<int:instance_id>/validate')
@permission_required('settings.manage_integrations')
def validate_instance(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)

    try:
        result = validate_alertmanager_instance(instance)
    except Exception as exc:  # pragma: no cover - defensive validation boundary
        logger.exception('Alertmanager validation failed for %s.', instance_id)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_instance_validation_failed',
            status='error',
            title='Alertmanager validation failed',
            message=f'KAORI could not validate {instance.name}.',
            detail='Review endpoint reachability, authentication, TLS settings, and KAORI logs before retrying.',
            metadata={
                'reason': type(exc).__name__,
            },
            queue_feedback=not _is_htmx_request(),
        )
    else:
        if result.get('connected'):
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_validated',
                status='success' if result.get('readiness_status') == 'ready' else 'warning',
                title='Alertmanager validation completed',
                message=f'{instance.name} responded and its API capability profile was evaluated.',
                detail=result.get('reason') or 'Alertmanager validation completed.',
                metadata={
                    'version': result.get('version'),
                    'response_time_ms': result.get('response_time_ms'),
                    'readiness_status': result.get('readiness_status'),
                    'capabilities': result.get('capabilities', []),
                },
                queue_feedback=not _is_htmx_request(),
            )
        else:
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_validation_failed',
                status='error',
                title='Alertmanager validation failed',
                message=f'KAORI could not validate {instance.name}.',
                detail=result.get('error') or 'Review endpoint reachability, authentication, and TLS settings.',
                metadata={
                    'reason': result.get('reason'),
                    'failure_code': result.get('failure_code'),
                    'endpoint_host': result.get('endpoint_host'),
                    'endpoint_port': result.get('endpoint_port'),
                    'request_path': result.get('request_path'),
                },
                queue_feedback=not _is_htmx_request(),
            )

    if _is_htmx_request():
        return _render_instance_partial(
            'alertmanager/partials/_detail_validation_content.html',
            instance,
            operation_feedback=feedback,
            validation_scope_oob=True,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#validation')


@alertmanager_bp.post('/instances/<int:instance_id>/bindings')
@permission_required('settings.manage_integrations')
def create_binding(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    form = parse_alertmanager_binding_form(request.form)
    is_htmx = _is_htmx_request()
    if form.scope_type == 'kubernetes_cluster' and get_cluster_by_id(form.scope_key) is None:
        error = 'Select a managed cluster that still exists in KAORI inventory.'
    else:
        error = None
    try:
        if error:
            raise ValueError(error)
        binding = add_alertmanager_binding(instance=instance, form=form)
    except ValueError as exc:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_create_rejected',
            status='error',
            title='Alertmanager binding not saved',
            message=f'KAORI could not bind {instance.name} to the requested scope.',
            detail=str(exc),
            metadata={
                'scope_type': form.scope_type,
                'scope_key': form.scope_key,
                'binding_role': form.binding_role,
                'priority': form.priority,
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:  # pragma: no cover - defensive database boundary
        logger.exception('Alertmanager binding creation failed for instance %s.', instance_id)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_create_failed',
            status='error',
            title='Alertmanager binding not saved',
            message=f'KAORI could not bind {instance.name} to the requested scope.',
            detail='Review KAORI logs and database connectivity before retrying the binding operation.',
            metadata={
                'scope_type': form.scope_type,
                'scope_key': form.scope_key,
                'binding_role': form.binding_role,
                'priority': form.priority,
                'reason': type(exc).__name__,
            },
            queue_feedback=not is_htmx,
        )
    else:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_created',
            status='success',
            title='Alertmanager binding saved',
            message=f'{instance.name} is now available to the selected operational scope.',
            detail=f'{binding.asset_type}:{binding.asset_key} is mapped as {binding.binding_role} with priority {binding.priority}.',
            metadata={
                'binding_id': binding.id,
                'scope_type': binding.asset_type,
                'scope_key': binding.asset_key,
                'binding_role': binding.binding_role,
                'priority': binding.priority,
            },
            queue_feedback=not is_htmx,
        )

    if is_htmx:
        return _render_instance_partial(
            'alertmanager/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#scope')



@alertmanager_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/selector')
@permission_required('settings.manage_integrations')
def update_binding_selector(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    binding = get_alertmanager_binding(binding_id)
    if instance is None or binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    is_htmx = _is_htmx_request()
    selector_label = request.form.get('selector_label', '').strip() or None
    selector_value = request.form.get('selector_value', '').strip() or None
    selector_operator = request.form.get('selector_operator', '=').strip() or '='
    try:
        update_alertmanager_binding_selector(
            instance=instance,
            binding=binding,
            selector_label=selector_label,
            selector_value=selector_value,
            selector_operator=selector_operator,
        )
    except ValueError as exc:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_selector_update_rejected',
            status='error',
            title='Alert identity not updated',
            message='KAORI could not save the Alertmanager binding selector.',
            detail=str(exc),
            metadata={'binding_id': binding.id},
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Alertmanager binding selector update failed for binding %s.', binding_id)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_selector_update_failed',
            status='error',
            title='Alert identity not updated',
            message='KAORI could not persist the Alertmanager binding selector.',
            detail='Review KAORI logs and database connectivity before retrying.',
            metadata={'binding_id': binding.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_selector_updated',
            status='success',
            title='Alert identity updated',
            message='The Alertmanager binding selector was saved.',
            detail='Binding readiness returned to Validation Required. Validate the binding before operational use.',
            metadata={
                'binding_id': binding.id,
                'selector_label': selector_label,
                'selector_operator': selector_operator,
                'selector_value': selector_value,
            },
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id) + '#scope')


@alertmanager_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/validate')
@permission_required('settings.manage_integrations')
def validate_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    binding = get_alertmanager_binding(binding_id)
    if instance is None or binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    result = validate_alertmanager_binding(instance=instance, binding=binding)
    feedback = record_instance_activity(
        user_id=int(current_user.id),
        instance=instance,
        event_type='alertmanager_binding_validated',
        status='success' if result['status'] == 'ready' else 'warning',
        title='Alertmanager binding validation completed',
        message=result['message'],
        detail=f"Binding status: {result['status'].replace('_', ' ').title()}.",
        metadata={'binding_id': binding.id, **result},
        queue_feedback=not _is_htmx_request(),
    )
    if _is_htmx_request():
        return _render_instance_partial(
            'alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id) + '#scope')

@alertmanager_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/delete')
@permission_required('settings.manage_integrations')
def remove_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    is_htmx = _is_htmx_request()
    binding = get_alertmanager_binding(binding_id)
    if binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    binding_metadata = {
        'binding_id': binding.id,
        'scope_type': binding.asset_type,
        'scope_key': binding.asset_key,
    }
    try:
        removed_binding = remove_alertmanager_binding(binding_id)
    except Exception as exc:
        logger.exception('Alertmanager binding deletion failed for binding %s.', binding_id)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_delete_failed',
            status='error',
            title='Alertmanager binding not removed',
            message=f'KAORI could not remove the selected binding from {instance.name}.',
            detail='Review KAORI logs and database connectivity before retrying the binding removal.',
            metadata={**binding_metadata, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        if removed_binding is None:
            abort(404)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_deleted',
            status='success',
            title='Alertmanager binding removed',
            message=f'{instance.name} is no longer mapped to the selected operational scope.',
            detail=f'{binding.asset_type}:{binding.asset_key} was removed.',
            metadata=binding_metadata,
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'alertmanager/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#scope')

@alertmanager_bp.post('/instances/<int:instance_id>/delete')
@permission_required('settings.manage_integrations')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    instance_name = instance.name
    is_htmx = _is_htmx_request()
    try:
        remove_alertmanager_instance(instance)
    except ValueError as exc:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_instance_delete_rejected',
            status='error',
            title='Alertmanager instance not deleted',
            message=f'{instance_name} still has active asset bindings.',
            detail=str(exc),
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial('alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback)
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#scope')
    except Exception as exc:
        logger.exception('Alertmanager instance deletion failed for %s.', instance_id)
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_instance_delete_failed',
            status='error',
            title='Alertmanager instance not deleted',
            message=f'KAORI could not delete {instance_name}.',
            detail='Review KAORI logs and database connectivity before retrying the deletion.',
            metadata={'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial('alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback)
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#scope')

    record_instance_activity(
        user_id=int(current_user.id),
        instance=None,
        event_type='alertmanager_instance_deleted',
        status='success',
        title='Alertmanager instance deleted',
        message=f'{instance_name} was removed from the integration registry.',
        detail='Historical operational activity remains available in Activity Audit Log.',
        metadata={'instance_id': instance_id, 'instance_name': instance_name},
        queue_feedback=True,
    )
    location = url_for('integrations.alertmanager')
    return _htmx_redirect(location) if is_htmx else redirect(location)

@alertmanager_bp.route('/cluster/<string:cluster_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def cluster_alertmanager_config(cluster_id: str) -> ResponseReturnValue:
    cluster = get_cluster_by_id(cluster_id)
    if cluster is None:
        abort(404)
    instance = materialize_legacy_cluster_config(cluster_id)
    if instance is not None:
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id))
    return redirect(url_for('integrations.bind_alertmanager_source', scope_key=cluster_id))


@alertmanager_bp.post('/cluster/<string:cluster_id>/test')
@permission_required('settings.manage_integrations')
def test_cluster_alertmanager(cluster_id: str) -> ResponseReturnValue:
    cluster = get_cluster_by_id(cluster_id)
    if cluster is None:
        abort(404)
    instance = materialize_legacy_cluster_config(cluster_id)
    try:
        result = test_alertmanager_connection(cluster_id=cluster_id)
    except Exception as exc:  # pragma: no cover - defensive compatibility boundary
        logger.exception('Alertmanager compatibility connection test failed for cluster %s.', cluster_id)
        result = {
            'connected': False,
            'error': 'KAORI could not complete the Alertmanager connection test.',
            'reason': 'Review endpoint reachability, authentication, TLS settings, scope bindings, and KAORI logs.',
            'failure_code': type(exc).__name__,
        }
    connected = bool(result.get('connected'))
    feedback = record_instance_activity(
        user_id=int(current_user.id),
        instance=instance,
        event_type='alertmanager_connection_test' if connected else 'alertmanager_connection_test_failed',
        status='success' if connected else 'error',
        title='Alertmanager connection verified' if connected else 'Alertmanager connection test failed',
        message=(
            f'KAORI reached the Alertmanager connection bound to {cluster.name}.'
            if connected
            else f'KAORI could not reach an Alertmanager connection for {cluster.name}.'
        ),
        detail=(
            result.get('reason')
            or result.get('error')
            or 'Review endpoint reachability, authentication, TLS settings, and scope bindings.'
        ),
        metadata={
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'version': result.get('version'),
            'response_time_ms': result.get('response_time_ms'),
            'failure_code': result.get('failure_code'),
            'compatibility_route': True,
        },
        queue_feedback=False,
    )
    if _is_htmx_request():
        return render_template(
            'components/navigation/_quick_sync_result.html',
            **feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    return jsonify(
        {
            'success': result.get('connected', False),
            'version': result.get('version', 'unknown'),
            'response_time_ms': result.get('response_time_ms', 0),
            'error': result.get('error'),
            'reason': result.get('reason'),
            'failure_code': result.get('failure_code'),
        }
    )
