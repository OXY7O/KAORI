from __future__ import annotations

import json
import logging

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.artifact_registry.webhooks import disable_webhook, generate_webhook_token
from app.integrations.deletion import DeletionBlocked
from app.integrations.registry.providers.harbor.application.forms import HarborInstanceForm
from app.integrations.registry.providers.harbor.application.presentation import (
    HarborIndexQuery,
    build_detail_context,
    build_index_context,
)
from app.integrations.registry.providers.harbor.application.registration import (
    issue_registration_proof,
    verify_registration_proof,
)
from app.integrations.registry.providers.harbor.application.service import (
    create_harbor_instance,
    delete_harbor_instance,
    get_harbor_instance,
    test_harbor_connection,
    update_harbor_instance,
)
from app.integrations.registry.providers.harbor.application.workspace_web import (
    detail_query_from_request,
    queue_full_validation,
    queue_runtime_refresh,
)
from app.integrations.registry.providers.harbor.exceptions import HarborError
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    snapshot_feedback_for_user,
    validate_snapshot_access,
    validation_poll_response,
)
from app.models.harbor import HarborInstance
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.security.credentials import CredentialEncryptionError

logger = logging.getLogger(__name__)

harbor_bp = Blueprint('harbor', __name__, url_prefix='/integrations/registry/harbor')


def _instance_or_404(instance_id: int) -> HarborInstance:
    instance = get_harbor_instance(instance_id)
    if instance is None:
        abort(404)
    return instance


def _queue_feedback(*, event_type: str, status: str, title: str, message: str, detail: str, action_url: str) -> None:
    record_operational_activity(
        user_id=int(current_user.id),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url,
        action_label='Open Harbor Connection',
        action_icon='package',
        queue_feedback=True,
    )


@harbor_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    context = build_index_context(
        HarborIndexQuery(
            tab=request.args.get('tab', 'coverage').strip(),
            query=request.args.get('q', '').strip(),
            environment=request.args.get('environment', '').strip(),
            readiness=request.args.get('readiness', '').strip(),
            compatibility=request.args.get('compatibility', '').strip(),
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
            coverage_query=request.args.get('coverage_q', '').strip(),
            coverage_environment=request.args.get('coverage_environment', '').strip(),
            coverage_status=request.args.get('coverage_status', '').strip(),
            coverage_page=request.args.get('coverage_page', 1, type=int) or 1,
            coverage_per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
        )
    )
    context['notification_context'] = get_navigation_notification_context(user_id=int(current_user.id))
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'harbor-integration-coverage':
            return render_template(
                'integrations/registry/providers/harbor/partials/_coverage.html',
                **context,
            )
        if target == 'harbor-connection-registry':
            return render_template(
                'integrations/registry/providers/harbor/partials/_registry.html',
                **context,
            )
    return render_template('integrations/registry/providers/harbor/index.html', **context)


@harbor_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def new_instance() -> ResponseReturnValue:
    form = HarborInstanceForm()
    registration_proof = str(request.form.get('connection_test_proof') or '')
    connection_error = None

    if form.validate_on_submit():
        values = form.to_input()
        action = str(request.form.get('action') or 'save').strip().lower()
        if action == 'test':
            try:
                test_harbor_connection(values)
                registration_proof = issue_registration_proof(values=values, user_id=int(current_user.id))
            except (HarborError, ValueError) as exc:
                connection_error = str(exc)
                registration_proof = ''
        elif action == 'save':
            verified, verification_message = verify_registration_proof(
                token=registration_proof,
                values=values,
                user_id=int(current_user.id),
            )
            if not verified:
                connection_error = verification_message
            else:
                try:
                    instance = create_harbor_instance(values)
                except (CredentialEncryptionError, SQLAlchemyError, ValueError) as exc:
                    logger.exception('Could not register Harbor connection.')
                    connection_error = str(exc)
                else:
                    _queue_feedback(
                        event_type='harbor_provider_registered',
                        status='success',
                        title='Harbor Connection Registered',
                        message=f'{instance.name} is registered as a reusable Registry provider connection.',
                        detail='Test Connection evidence is not readiness. Run Full Validation to establish compatibility and required Harbor capability evidence.',
                        action_url=url_for('harbor.instance_detail', instance_id=instance.id),
                    )
                    return redirect(url_for('harbor.instance_detail', instance_id=instance.id))

    return render_template(
        'integrations/registry/providers/harbor/instance_form.html',
        form=form,
        registration_proof=registration_proof,
        connection_error=connection_error,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@harbor_bp.post('/instances/test-connection')
@permission_required('integrations.manage')
def test_new_instance_connection() -> ResponseReturnValue:
    form = HarborInstanceForm()
    connected = False
    registration_proof = ''

    if not form.validate_on_submit():
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='harbor_connection_test_failed',
            status='error',
            title='Harbor connection test failed',
            message='Review the submitted Harbor connection fields before testing this provider.',
            detail='The submitted form did not satisfy the Harbor connection contract.',
            action_url=url_for('harbor.new_instance'),
            action_label='Review Harbor form',
            action_icon='package',
            metadata={'fields': sorted(form.errors), 'draft_connection': True},
            queue_feedback=False,
        )
    else:
        values = form.to_input()
        try:
            result = test_harbor_connection(values)
        except (HarborError, ValueError) as exc:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='harbor_connection_test_failed',
                status='error',
                title='Harbor connection test failed',
                message=str(exc),
                detail='Review the Harbor endpoint, authentication, TLS trust, and system-info reachability.',
                action_url=url_for('harbor.new_instance'),
                action_label='Review Harbor form',
                action_icon='package',
                metadata={'draft_connection': True, 'submitted_name': values.name},
                queue_feedback=False,
            )
        else:
            connected = True
            registration_proof = issue_registration_proof(values=values, user_id=int(current_user.id))
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='harbor_connection_test',
                status='success',
                title='Harbor API connection verified',
                message='KAORI reached Harbor and confirmed provider identity from the API.',
                detail=(
                    f'Harbor reported version {result.get("version") or "unknown"} in '
                    f'{int(result.get("response_time_ms") or 0)} ms. '
                    'This Test Connection proves identity and reachability only. Register the connection, then run Full Validation for readiness.'
                ),
                action_url=url_for('harbor.new_instance'),
                action_label='Review Harbor form',
                action_icon='package',
                metadata={
                    'draft_connection': True,
                    'submitted_name': values.name,
                    'detected_version': result.get('version'),
                    'response_time_ms': result.get('response_time_ms'),
                },
                queue_feedback=False,
            )

    response = make_response(
        render_template(
            'integrations/registry/providers/harbor/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {'harbor-connection-tested': {'connected': connected, 'proof': registration_proof}},
        separators=(',', ':'),
    )
    return response


@harbor_bp.post('/instances/<int:instance_id>/webhook/token')
@permission_required('integrations.manage')
def webhook_token(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    token = generate_webhook_token(int(instance.integration_instance.id))
    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'artifact_registry/partials/_webhook_token_created.html',
            webhook_token=token,
        )
    return {'token': token, 'display_once': True}


@harbor_bp.post('/instances/<int:instance_id>/webhook/disable')
@permission_required('integrations.manage')
def webhook_disable(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    disable_webhook(int(instance.integration_instance.id))
    _queue_feedback(
        event_type='harbor_webhook_disabled',
        status='success',
        title='Registry Webhook Disabled',
        message=f'Webhook admission is disabled for {instance.name}.',
        detail='Scheduled Registry reconciliation remains the correctness authority.',
        action_url=url_for('harbor.instance_detail', instance_id=instance.id) + '#configuration',
    )
    return redirect(url_for('harbor.instance_detail', instance_id=instance.id) + '#configuration')


@harbor_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def edit_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = HarborInstanceForm(obj=instance, existing_instance=instance)
    if request.method == 'GET':
        form.password.data = ''

    if form.validate_on_submit():
        try:
            updated = update_harbor_instance(instance, form.to_input(existing_instance=instance))
        except (CredentialEncryptionError, SQLAlchemyError, ValueError) as exc:
            logger.exception('Could not update Harbor connection %s.', instance_id)
            _queue_feedback(
                event_type='harbor_provider_update_failed',
                status='error',
                title='Harbor Connection Not Updated',
                message=f'KAORI could not update {instance.name}.',
                detail=str(exc),
                action_url=url_for('harbor.edit_instance', instance_id=instance.id),
            )
        else:
            _queue_feedback(
                event_type='harbor_provider_updated',
                status='success',
                title='Harbor Connection Updated',
                message=f'{updated.name} configuration was saved.',
                detail='Connection-sensitive changes reset provider readiness. Run Full Validation before operational use.',
                action_url=url_for('harbor.instance_detail', instance_id=updated.id),
            )
            return redirect(url_for('harbor.instance_detail', instance_id=updated.id))

    return render_template(
        'integrations/registry/providers/harbor/instance_form.html',
        form=form,
        instance=instance,
        registration_proof='',
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@harbor_bp.post('/instances/<int:instance_id>/test-configuration')
@permission_required('integrations.manage')
def test_instance_configuration(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = HarborInstanceForm(existing_instance=instance)
    if not form.validate_on_submit():
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='harbor_configuration_test_failed',
            status='error',
            title='Harbor configuration test failed',
            message='Review the submitted Harbor connection fields before testing this configuration.',
            detail='The submitted form did not satisfy the Harbor connection contract.',
            action_url=url_for('harbor.edit_instance', instance_id=instance.id),
            action_label='Review Harbor configuration',
            action_icon='settings-2',
            metadata={'fields': sorted(form.errors), 'instance_id': instance.id},
            queue_feedback=False,
        )
    else:
        values = form.to_input(existing_instance=instance)
        try:
            result = test_harbor_connection(values)
        except (HarborError, ValueError) as exc:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='harbor_configuration_test_failed',
                status='error',
                title='Harbor configuration test failed',
                message=str(exc),
                detail='Review the Harbor endpoint, authentication, TLS trust, and system-info reachability.',
                action_url=url_for('harbor.edit_instance', instance_id=instance.id),
                action_label='Review Harbor configuration',
                action_icon='settings-2',
                metadata={'instance_id': instance.id},
                queue_feedback=False,
            )
        else:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='harbor_configuration_test',
                status='success',
                title='Harbor configuration reachable',
                message='KAORI reached Harbor with the submitted effective configuration.',
                detail=(
                    f'Harbor reported version {result.get("version") or "unknown"} in '
                    f'{int(result.get("response_time_ms") or 0)} ms. Save changes, then run Full Validation.'
                ),
                action_url=url_for('harbor.edit_instance', instance_id=instance.id),
                action_label='Review Harbor configuration',
                action_icon='settings-2',
                metadata={
                    'instance_id': instance.id,
                    'detected_version': result.get('version'),
                    'response_time_ms': result.get('response_time_ms'),
                },
                queue_feedback=False,
            )
    return render_template(
        'integrations/registry/providers/harbor/partials/_connection_test_result.html',
        connection_feedback=feedback,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@harbor_bp.get('/instances/<int:instance_id>')
@permission_required('integrations.manage')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    validation_task_id = get_active_validation_task_id(
        integration_type='registry',
        operation='full_validation',
        integration_instance_id=instance.integration_instance_id,
    )
    runtime_task_id = get_active_validation_task_id(
        integration_type='registry',
        operation='runtime_refresh',
        integration_instance_id=instance.integration_instance_id,
    )
    return render_template(
        'integrations/registry/providers/harbor/instance_detail.html',
        **build_detail_context(instance, detail_query_from_request()),
        validation_job=build_validation_snapshot(validation_task_id) if validation_task_id else None,
        runtime_refresh_job=build_validation_snapshot(runtime_task_id) if runtime_task_id else None,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@harbor_bp.get('/instances/<int:instance_id>/capabilities/registry')
@permission_required('integrations.manage')
def capability_registry(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    context = build_detail_context(instance, detail_query_from_request())
    validation_task_id = get_active_validation_task_id(
        integration_type='registry',
        operation='full_validation',
        integration_instance_id=instance.integration_instance_id,
    )
    context['validation_job'] = build_validation_snapshot(validation_task_id) if validation_task_id else None
    return render_template('integrations/registry/providers/harbor/partials/_capability_registry.html', **context)


@harbor_bp.post('/instances/<int:instance_id>/validate')
@permission_required('integrations.manage')
def validate_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    validation_job, feedback = queue_full_validation(instance, user_id=int(current_user.id), is_htmx=is_htmx)
    if is_htmx:
        context = build_detail_context(instance, detail_query_from_request())
        context.update(validation_job=validation_job, operation_feedback=feedback)
        return render_template('integrations/registry/providers/harbor/partials/_detail_validation.html', **context)
    return redirect(url_for('harbor.instance_detail', instance_id=instance.id, _anchor='validation'))


@harbor_bp.get('/instances/<int:instance_id>/validation/status/<string:task_id>')
@permission_required('integrations.manage')
def validation_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='registry',
        integration_instance_id=instance.integration_instance_id,
    ):
        abort(404)
    context = build_detail_context(instance, detail_query_from_request())
    context.update(
        validation_job=snapshot,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
    )
    content = render_template('integrations/registry/providers/harbor/partials/_detail_validation.html', **context)
    return validation_poll_response(content, snapshot=snapshot)


@harbor_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('integrations.manage')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    runtime_refresh_job, feedback = queue_runtime_refresh(instance, user_id=int(current_user.id), is_htmx=is_htmx)
    if is_htmx:
        context = build_detail_context(instance, detail_query_from_request())
        context.update(
            runtime_refresh_job=runtime_refresh_job,
            operation_feedback=feedback,
            runtime_history_oob=True,
        )
        return render_template('integrations/registry/providers/harbor/partials/_detail_runtime.html', **context)
    return redirect(url_for('harbor.instance_detail', instance_id=instance.id, _anchor='runtime'))


@harbor_bp.get('/instances/<int:instance_id>/runtime/refresh/status/<string:task_id>')
@permission_required('integrations.manage')
def runtime_refresh_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='registry',
        integration_instance_id=instance.integration_instance_id,
    ):
        abort(404)
    context = build_detail_context(instance)
    context.update(
        runtime_refresh_job=snapshot,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        runtime_history_oob=True,
    )
    content = render_template('integrations/registry/providers/harbor/partials/_detail_runtime.html', **context)
    return validation_poll_response(content, snapshot=snapshot)


@harbor_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('integrations.manage')
def runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    context = build_detail_context(instance, detail_query_from_request())
    return render_template(
        'integrations/partials/_runtime_history.html',
        runtime_history=context['runtime_history'],
        runtime_history_id='harbor-runtime-history',
        runtime_history_loading_id='harbor-history-loading',
        runtime_history_url=url_for('harbor.runtime_history', instance_id=instance.id),
        runtime_history_endpoint='harbor.runtime_history',
        runtime_history_route_args={'instance_id': instance.id},
        runtime_history_detail_url=url_for('harbor.instance_detail', instance_id=instance.id),
        runtime_history_detail_endpoint='harbor.instance_detail',
        runtime_history_filters_enabled=True,
        provider_label='Harbor',
    )



@harbor_bp.get('/instances/<int:instance_id>/bindings/registry')
@permission_required('integrations.manage')
def binding_registry(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    return render_template(
        'integrations/registry/providers/harbor/partials/_binding_registry.html',
        **build_detail_context(instance, detail_query_from_request()),
    )


@harbor_bp.post('/instances/<int:instance_id>/delete')
@permission_required('integrations.manage')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    instance_name = instance.name
    try:
        summary = delete_harbor_instance(instance)
    except DeletionBlocked as exc:
        logger.warning('Harbor deletion blocked for %s: %s', instance_id, exc)
        _queue_feedback(
            event_type='harbor_instance_delete_rejected',
            status='warning',
            title='Harbor Connection Deletion Blocked',
            message=f'{instance_name} still has active operational dependencies.',
            detail=str(exc),
            action_url=url_for('harbor.instance_detail', instance_id=instance_id, _anchor='inventory'),
        )
        return redirect(url_for('harbor.instance_detail', instance_id=instance_id, _anchor='inventory'))
    except SQLAlchemyError:
        logger.exception('Harbor instance deletion failed for %s.', instance_id)
        _queue_feedback(
            event_type='harbor_instance_delete_failed',
            status='error',
            title='Harbor Connection Not Deleted',
            message=f'KAORI could not delete {instance_name}.',
            detail='Review database connectivity and dependent committed Registry records before retrying.',
            action_url=url_for('harbor.instance_detail', instance_id=instance_id, _anchor='inventory'),
        )
        return redirect(url_for('harbor.instance_detail', instance_id=instance_id, _anchor='inventory'))

    record_operational_activity(
        user_id=int(current_user.id),
        event_type='harbor_instance_deleted',
        status='success',
        title='Harbor Connection Deleted',
        message=f'{instance_name} was removed from the KAORI Registry integration.',
        detail=(
            f'Removed {summary["asset_bindings"]} binding(s) targeting this Registry instance. '
            'Harbor projects, repositories, artifacts, policies, and other provider-owned resources were not changed. '
            'Reusable observability sources, runtime history, JobExecution history, and Activity Audit evidence remain retained.'
        ),
        action_url=url_for('harbor.index', tab='registry'),
        action_label='Open Harbor Registry',
        action_icon='package',
        metadata={'instance_name': instance_name, **summary},
        queue_feedback=True,
    )
    return redirect(url_for('harbor.index', tab='registry'))
