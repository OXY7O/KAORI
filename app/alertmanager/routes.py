from __future__ import annotations

import logging
from dataclasses import replace

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.alertmanager.forms import (
    AlertmanagerBindingForm,
    parse_alertmanager_binding_form,
    parse_alertmanager_instance_form,
)
from app.alertmanager.notifications import record_instance_activity
from app.alertmanager.presentation import build_instance_context, build_runtime_history_context
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
    validate_alertmanager_instance,
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


@alertmanager_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def new_instance() -> ResponseReturnValue:
    initial_cluster_id = request.values.get('cluster_id', '').strip()
    initial_cluster = get_cluster_by_id(initial_cluster_id) if initial_cluster_id else None
    draft_form = None
    form_error = None

    if request.method == 'POST':
        form = parse_alertmanager_instance_form(request.form)
        if not form.name and initial_cluster is not None:
            form = replace(form, name=f'{initial_cluster.name} Alertmanager', deployment_type='cluster_managed')
        draft_form = form
        try:
            initial_binding = (
                AlertmanagerBindingForm(
                    scope_type='kubernetes_cluster',
                    scope_key=initial_cluster.id,
                    binding_role='primary',
                    priority=100,
                    enabled=True,
                )
                if initial_cluster is not None
                else None
            )
            instance = create_alertmanager_instance(
                form=form,
                initial_binding=initial_binding,
            )
        except ValueError as exc:
            form_error = str(exc)
            record_instance_activity(
                user_id=int(current_user.id),
                instance=None,
                event_type='alertmanager_instance_create_rejected',
                status='error',
                title='Alertmanager instance not created',
                message='KAORI could not create the Alertmanager instance.',
                detail=str(exc),
                metadata={'cluster_id': initial_cluster_id or None},
            )
        except Exception as exc:  # pragma: no cover - defensive database boundary
            form_error = 'KAORI could not save the Alertmanager instance. Review application logs and database connectivity before retrying.'
            logger.exception('Alertmanager instance creation failed.')
            record_instance_activity(
                user_id=int(current_user.id),
                instance=None,
                event_type='alertmanager_instance_create_failed',
                status='error',
                title='Alertmanager instance not created',
                message='KAORI could not save the Alertmanager instance.',
                detail='Review application logs and database connectivity before retrying.',
                metadata={'reason': type(exc).__name__},
            )
        else:
            record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_created',
                status='success',
                title='Alertmanager instance created',
                message=f'{instance.name} is now registered as an Alertmanager source.',
                detail='Run full validation, review readiness, then create scope bindings before operational use.',
                metadata={'initial_cluster_id': initial_cluster_id or None},
            )
            return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id))

    return render_template(
        'alertmanager/instance_form.html',
        **build_instance_context(),
        initial_cluster=initial_cluster,
        draft_form=draft_form,
        form_error=form_error,
    )


@alertmanager_bp.post('/instances/test-connection')
@permission_required('settings.manage_integrations')
def test_new_instance_connection() -> ResponseReturnValue:
    form = parse_alertmanager_instance_form(request.form)
    result = test_alertmanager_form_connection(form)

    if result.get('connected'):
        record_instance_activity(
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
            },
            queue_feedback=False,
        )
    else:
        record_instance_activity(
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
            },
            queue_feedback=False,
        )

    return render_template(
        'alertmanager/partials/_connection_test_result.html',
        connection_test=result,
    )


@alertmanager_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)

    if request.method == 'POST':
        form = parse_alertmanager_instance_form(request.form)
        try:
            instance = save_alertmanager_instance(form=form, instance=instance)
        except ValueError as exc:
            record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_update_rejected',
                status='error',
                title='Alertmanager instance not updated',
                message=f'KAORI could not update {instance.name}.',
                detail=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive database boundary
            logger.exception('Alertmanager instance update failed for %s.', instance_id)
            record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_update_failed',
                status='error',
                title='Alertmanager instance not updated',
                message=f'KAORI could not update {instance.name}.',
                detail='Review application logs and database connectivity before retrying.',
                metadata={'reason': type(exc).__name__},
            )
        else:
            record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_updated',
                status='success',
                title='Alertmanager instance updated',
                message=f'{instance.name} connection settings were saved.',
                detail='Readiness is now Validation Required until a full validation completes.',
            )
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id))

    return render_template(
        'alertmanager/instance_form.html',
        **build_instance_context(instance),
        initial_cluster=None,
    )


@alertmanager_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('settings.manage_integrations')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)

    result, state, _observation = refresh_provider_runtime(runtime_adapter, instance, trigger_type="manual")
    record_instance_activity(
        user_id=int(current_user.id),
        instance=instance,
        event_type='alertmanager_runtime_refreshed' if result.connected else 'alertmanager_runtime_refresh_failed',
        status='success' if state.health.status == 'healthy' else ('warning' if state.health.status == 'degraded' else 'error'),
        title='Alertmanager runtime refreshed',
        message=f'{instance.name} runtime health is {state.health.status}.',
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
    return render_template(
        'alertmanager/partials/_runtime_refresh_response.html',
        instance=instance,
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

    result = validate_alertmanager_instance(instance)
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
            queue_feedback=request.headers.get('HX-Request') != 'true',
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
            queue_feedback=request.headers.get('HX-Request') != 'true',
        )

    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'components/navigation/_quick_sync_result.html',
            **feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id))


@alertmanager_bp.post('/instances/<int:instance_id>/bindings')
@permission_required('settings.manage_integrations')
def create_binding(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    form = parse_alertmanager_binding_form(request.form)
    if form.scope_type == 'kubernetes_cluster' and get_cluster_by_id(form.scope_key) is None:
        error = 'The selected Kubernetes cluster does not exist.'
    else:
        error = None
    try:
        if error:
            raise ValueError(error)
        binding = add_alertmanager_binding(instance=instance, form=form)
    except ValueError as exc:
        record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_create_rejected',
            status='error',
            title='Alertmanager binding not saved',
            message=f'KAORI could not bind {instance.name} to the requested scope.',
            detail=str(exc),
            metadata={'scope_type': form.scope_type, 'scope_key': form.scope_key},
        )
    else:
        record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_created',
            status='success',
            title='Alertmanager binding saved',
            message=f'{instance.name} is now available to the selected operational scope.',
            detail=f'{binding.asset_type}:{binding.asset_key} is mapped as {binding.binding_role}.',
            metadata={
                'binding_id': binding.id,
                'scope_type': binding.asset_type,
                'scope_key': binding.asset_key,
                'binding_role': binding.binding_role,
                'priority': binding.priority,
            },
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id))


@alertmanager_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/delete')
@permission_required('settings.manage_integrations')
def remove_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    binding = get_alertmanager_binding(binding_id)
    if binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    removed_binding = remove_alertmanager_binding(binding_id)
    if removed_binding is None:
        abort(404)
    record_instance_activity(
        user_id=int(current_user.id),
        instance=instance,
        event_type='alertmanager_binding_deleted',
        status='success',
        title='Alertmanager binding removed',
        message=f'{instance.name} is no longer mapped to the selected operational scope.',
        detail=f'{binding.asset_type}:{binding.asset_key} was removed.',
        metadata={
            'binding_id': binding.id,
            'scope_type': binding.asset_type,
            'scope_key': binding.asset_key,
        },
    )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id))


@alertmanager_bp.post('/instances/<int:instance_id>/delete')
@permission_required('settings.manage_integrations')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    instance_name = instance.name
    try:
        remove_alertmanager_instance(instance)
    except ValueError as exc:
        record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_instance_delete_rejected',
            status='error',
            title='Alertmanager instance not deleted',
            message=f'{instance_name} still has active asset bindings.',
            detail=str(exc),
        )
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id))

    record_instance_activity(
        user_id=int(current_user.id),
        instance=None,
        event_type='alertmanager_instance_deleted',
        status='success',
        title='Alertmanager instance deleted',
        message=f'{instance_name} was removed from the integration registry.',
        detail='Historical operational activity remains available in Activity Audit Log.',
        metadata={'instance_id': instance_id, 'instance_name': instance_name},
    )
    return redirect(url_for('integrations.alertmanager'))


@alertmanager_bp.route('/cluster/<string:cluster_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def cluster_alertmanager_config(cluster_id: str) -> ResponseReturnValue:
    cluster = get_cluster_by_id(cluster_id)
    if cluster is None:
        abort(404)
    instance = materialize_legacy_cluster_config(cluster_id)
    if instance is not None:
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id))
    return redirect(url_for('alertmanager.new_instance', cluster_id=cluster_id))


@alertmanager_bp.post('/cluster/<string:cluster_id>/test')
@permission_required('settings.manage_integrations')
def test_cluster_alertmanager(cluster_id: str) -> ResponseReturnValue:
    cluster = get_cluster_by_id(cluster_id)
    if cluster is None:
        abort(404)
    result = test_alertmanager_connection(cluster_id=cluster_id)
    if request.headers.get('HX-Request') == 'true':
        return jsonify(result)
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
