from __future__ import annotations

import json
import logging
from dataclasses import replace

from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, url_for
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
from app.alertmanager.service import (
    add_alertmanager_binding,
    binding_scope_validation_error,
    create_alertmanager_instance,
    get_alertmanager_binding,
    get_alertmanager_instance,
    get_cluster_by_id,
    remove_alertmanager_binding,
    remove_alertmanager_instance,
    save_alertmanager_instance,
    test_alertmanager_form_connection,
    update_alertmanager_binding_selector,
)
from app.common.http import is_htmx_request
from app.integrations.capability_registry import build_capability_registry_view
from app.integrations.deletion import DeletionBlocked
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    enqueue_binding_validation,
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
)
from app.notifications.service import get_navigation_notification_context
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

alertmanager_bp = Blueprint(
    'alertmanager',
    __name__,
    url_prefix='/integrations/alertmanager',
)


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response


def _instance_context(instance) -> dict:
    context = build_instance_context(instance)
    context['capability_registry'] = build_capability_registry_view(
        context.get('capability_rows', []),
        search_fields=('label', 'category', 'description'),
        distinguish_optional_gap=True,
    )
    validation_task_id = get_active_validation_task_id(
        provider_type='alertmanager',
        operation='full_validation',
        instance_id=instance.id,
    )
    context['validation_job'] = build_validation_snapshot(validation_task_id) if validation_task_id else None
    runtime_task_id = get_active_validation_task_id(
        provider_type='alertmanager',
        operation='runtime_refresh',
        instance_id=instance.id,
    )
    context['runtime_refresh_job'] = build_validation_snapshot(runtime_task_id) if runtime_task_id else None
    binding_job = None
    for binding in context.get('bindings', []):
        task_id = get_active_validation_task_id(
            provider_type='alertmanager',
            operation='binding_validation',
            instance_id=instance.id,
            binding_id=binding.id,
        )
        if task_id:
            binding_job = build_validation_snapshot(task_id)
            break
    context['binding_validation_job'] = binding_job
    return context


def _render_instance_partial(
    template_name: str,
    instance,
    *,
    operation_feedback: dict | None = None,
    **extra_context,
) -> str:
    context = _instance_context(instance)
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
    is_htmx = is_htmx_request()

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
                f'Status API responded in {result.get("response_time_ms", 0)} ms. '
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
        issue_registration_proof(form=form, user_id=int(current_user.id)) if result.get('connected') else ''
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


@alertmanager_bp.post('/instances/<int:instance_id>/test-configuration')
@permission_required('settings.manage_integrations')
def test_instance_configuration(instance_id: int) -> ResponseReturnValue:
    """Test submitted edit settings without mutating the saved instance."""
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    form = parse_alertmanager_instance_form(request.form)
    result = test_alertmanager_form_connection(form, existing_instance=instance)
    connected = bool(result.get('connected'))
    feedback = record_instance_activity(
        user_id=int(current_user.id),
        instance=instance,
        event_type='alertmanager_connection_test' if connected else 'alertmanager_connection_test_failed',
        status='success' if connected else 'error',
        title='Alertmanager configuration verified' if connected else 'Alertmanager configuration test failed',
        message=(
            f'KAORI reached the submitted settings for {instance.name}.'
            if connected
            else f'KAORI could not verify the submitted settings for {instance.name}.'
        ),
        detail=(
            f'Alertmanager {result.get("version") or "unknown"} responded in '
            f'{result.get("response_time_ms") or 0} ms. Save the configuration, then run Full Validation.'
            if connected
            else result.get('error')
            or result.get('reason')
            or 'Review endpoint, authentication, TLS, and network reachability.'
        ),
        metadata={
            'endpoint_host': result.get('endpoint_host'),
            'endpoint_port': result.get('endpoint_port'),
            'version': result.get('version'),
            'response_time_ms': result.get('response_time_ms'),
            'failure_code': result.get('failure_code'),
            'draft_update': True,
        },
        queue_feedback=False,
    )
    return render_template(
        'alertmanager/partials/_connection_test_result.html',
        connection_feedback=feedback,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@alertmanager_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    is_htmx = is_htmx_request()

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

    return render_template('alertmanager/instance_detail.html', **_instance_context(instance))


@alertmanager_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('settings.manage_integrations')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    is_htmx = is_htmx_request()
    try:
        runtime_refresh_job, created = enqueue_runtime_health_refresh(
            provider_type='alertmanager',
            instance_id=instance.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_runtime_refresh_queued'
            if created
            else 'alertmanager_runtime_refresh_already_running',
            status='info' if created else 'warning',
            title='Alertmanager runtime refresh queued' if created else 'Alertmanager runtime refresh already running',
            message=(
                f'KAORI queued a lightweight runtime refresh for {instance.name}.'
                if created
                else f'A runtime refresh is already running for {instance.name}.'
            ),
            detail=(
                'The runtime worker will check endpoint health without rebuilding capability evidence.'
                if created
                else 'KAORI kept the active task and did not enqueue a duplicate.'
            ),
            metadata={
                'task_id': runtime_refresh_job.get('task_id'),
                'queue': current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Alertmanager runtime refresh for %s.', instance_id)
        runtime_refresh_job = None
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_runtime_refresh_enqueue_failed',
            status='error',
            title='Alertmanager runtime refresh not queued',
            message=f'KAORI could not queue runtime health refresh for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-runtime worker before retrying.',
            metadata={'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'alertmanager/partials/_runtime_refresh_response.html',
            instance,
            operation_feedback=feedback,
            runtime_refresh_job=runtime_refresh_job,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#runtime')


@alertmanager_bp.get('/instances/<int:instance_id>/runtime/refresh/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def runtime_refresh_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='alertmanager',
        instance_id=instance.id,
    ):
        abort(404)
    return _render_instance_partial(
        'alertmanager/partials/_runtime_refresh_response.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        runtime_refresh_job=snapshot,
    )


@alertmanager_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('settings.manage_integrations')
def runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    page = request.args.get('page', default=1, type=int) or 1
    per_page = request.args.get('per_page', default=5, type=int) or 5
    history_trigger = request.args.get('history_trigger', default='', type=str) or ''
    history_health = request.args.get('history_health', default='', type=str) or ''
    history_readiness = request.args.get('history_readiness', default='', type=str) or ''
    return render_template(
        'alertmanager/partials/_runtime_history.html',
        instance=instance,
        runtime_history=build_runtime_history_context(
            instance,
            page=page,
            per_page=per_page,
            trigger_type=history_trigger,
            health_status=history_health,
            readiness=history_readiness,
        ),
    )


@alertmanager_bp.post('/instances/<int:instance_id>/validate')
@permission_required('settings.manage_integrations')
def validate_instance(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    is_htmx = is_htmx_request()
    try:
        validation_job, created = enqueue_instance_validation(
            provider_type='alertmanager',
            instance_id=instance.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_full_validation_queued'
            if created
            else 'alertmanager_full_validation_already_running',
            status='info' if created else 'warning',
            title='Alertmanager validation queued' if created else 'Alertmanager validation already running',
            message=(
                f'KAORI queued Full Validation for {instance.name}.'
                if created
                else f'Full Validation is already running for {instance.name}.'
            ),
            detail=(
                'The dedicated validation worker will rebuild API, capability, compatibility, and readiness evidence.'
                if created
                else 'KAORI kept the existing task and did not enqueue a duplicate validation job.'
            ),
            metadata={
                'task_id': validation_job.get('task_id'),
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Alertmanager Full Validation for %s.', instance_id)
        validation_job = None
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_full_validation_enqueue_failed',
            status='error',
            title='Alertmanager validation not queued',
            message=f'KAORI could not queue Full Validation for {instance.name}.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            metadata={'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'alertmanager/partials/_detail_validation_content.html',
            instance,
            operation_feedback=feedback,
            validation_job=validation_job,
            validation_scope_oob=True,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#validation')


@alertmanager_bp.get('/instances/<int:instance_id>/validation/capabilities')
@permission_required('settings.manage_integrations')
def instance_capability_registry(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    context = _instance_context(instance)
    context['capability_registry'] = build_capability_registry_view(
        context.get('capability_rows', []),
        query=request.args.get('query', ''),
        requirement=request.args.get('requirement', 'all'),
        status=request.args.get('status', 'all'),
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 5),
        search_fields=('label', 'category', 'description'),
        distinguish_optional_gap=True,
    )
    return render_template('alertmanager/partials/_capability_registry.html', **context)


@alertmanager_bp.get('/instances/<int:instance_id>/validate/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def instance_validation_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='alertmanager',
        instance_id=instance.id,
    ):
        abort(404)
    return _render_instance_partial(
        'alertmanager/partials/_detail_validation_content.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        validation_job=snapshot,
        validation_scope_oob=True,
    )


@alertmanager_bp.post('/instances/<int:instance_id>/bindings')
@permission_required('settings.manage_integrations')
def create_binding(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    form = parse_alertmanager_binding_form(request.form)
    is_htmx = is_htmx_request()
    error = binding_scope_validation_error(form.scope_type, form.scope_key)
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
    is_htmx = is_htmx_request()
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
            'alertmanager/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id) + '#scope')


@alertmanager_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/validate')
@permission_required('settings.manage_integrations')
def validate_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    binding = get_alertmanager_binding(binding_id)
    if instance is None or binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    is_htmx = is_htmx_request()
    try:
        validation_job, created = enqueue_binding_validation(
            provider_type='alertmanager',
            instance_id=instance.id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_validation_queued'
            if created
            else 'alertmanager_binding_validation_already_running',
            status='info' if created else 'warning',
            title='Alertmanager binding validation queued'
            if created
            else 'Alertmanager binding validation already running',
            message=(
                'KAORI queued the alert identity validation.'
                if created
                else 'The alert identity validation is already running.'
            ),
            detail=(
                'The validation worker will check the scope filter before this binding becomes eligible.'
                if created
                else 'KAORI kept the active task and did not enqueue a duplicate.'
            ),
            metadata={
                'task_id': validation_job.get('task_id'),
                'binding_id': binding.id,
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Could not enqueue Alertmanager binding validation for %s.', binding_id)
        validation_job = None
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_binding_validation_enqueue_failed',
            status='error',
            title='Alertmanager binding validation not queued',
            message='KAORI could not queue the alert identity validation.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            metadata={'binding_id': binding.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return _render_instance_partial(
            'alertmanager/partials/_detail_scope.html',
            instance,
            operation_feedback=feedback,
            binding_validation_job=validation_job,
        )
    return redirect(url_for('alertmanager.instance_detail', instance_id=instance.id) + '#scope')


@alertmanager_bp.get('/instances/<int:instance_id>/bindings/<int:binding_id>/validate/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def binding_validation_status(instance_id: int, binding_id: int, task_id: str) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    binding = get_alertmanager_binding(binding_id)
    if instance is None or binding is None or binding.integration_instance_id != instance.integration_instance_id:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='alertmanager',
        instance_id=instance.id,
        binding_id=binding.id,
    ):
        abort(404)
    return _render_instance_partial(
        'alertmanager/partials/_detail_scope.html',
        instance,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        binding_validation_job=snapshot,
    )


@alertmanager_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/delete')
@permission_required('settings.manage_integrations')
def remove_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    is_htmx = is_htmx_request()
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
    is_htmx = is_htmx_request()
    try:
        remove_alertmanager_instance(instance)
    except DeletionBlocked as exc:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=instance,
            event_type='alertmanager_instance_delete_rejected',
            status='warning',
            title='Alertmanager instance deletion blocked',
            message=f'{instance_name} still has active operational dependencies.',
            detail=str(exc),
            metadata={'active_jobs': exc.guard.active_jobs},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_instance_partial(
                'alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback
            )
        return redirect(url_for('alertmanager.instance_detail', instance_id=instance_id) + '#scope')
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
            return _render_instance_partial(
                'alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback
            )
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
            return _render_instance_partial(
                'alertmanager/partials/_detail_scope.html', instance, operation_feedback=feedback
            )
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
