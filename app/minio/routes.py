from __future__ import annotations

import json
import logging

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.deletion import DeletionBlocked
from app.integrations.minio.client import MinioConnectionError
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    snapshot_feedback_for_user,
    validate_snapshot_access,
)
from app.minio.forms import MinioInstanceForm
from app.minio.presentation import MinioIndexQuery, build_detail_context, build_index_context
from app.minio.registration import issue_registration_proof, verify_registration_proof
from app.minio.service import (
    create_minio_instance,
    delete_minio_instance,
    test_minio_connection,
    update_minio_instance,
)
from app.minio.workspace_web import detail_query_from_request, queue_full_validation, queue_runtime_refresh
from app.models.minio import MinioInstance
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.rbac.decorators import permission_required
from app.security.credentials import CredentialEncryptionError

logger = logging.getLogger(__name__)

minio_bp = Blueprint('minio', __name__, url_prefix='/integrations/minio')


def _instance_or_404(instance_id: int) -> MinioInstance:
    instance = MinioInstance.query.filter_by(id=instance_id).first()
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
        action_label='Open MinIO Connection',
        action_icon='database',
        queue_feedback=True,
    )


@minio_bp.get('/')
@permission_required('settings.manage_integrations')
def index() -> ResponseReturnValue:
    context = build_index_context(
        MinioIndexQuery(
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
        if target == 'minio-coverage-content':
            return render_template('minio/partials/_coverage_content.html', **context)
        if target == 'minio-registry-content':
            return render_template('minio/partials/_registry_content.html', **context)
    return render_template('minio/index.html', **context)


@minio_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def new_instance() -> ResponseReturnValue:
    form = MinioInstanceForm()
    registration_proof = str(request.form.get('connection_test_proof') or '')
    connection_result = None
    connection_error = None

    if form.validate_on_submit():
        values = form.to_input()
        action = str(request.form.get('action') or 'save').strip().lower()
        if action == 'test':
            try:
                connection_result = test_minio_connection(values)
                registration_proof = issue_registration_proof(values=values, user_id=int(current_user.id))
            except (MinioConnectionError, ValueError) as exc:
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
                    instance = create_minio_instance(values)
                except (CredentialEncryptionError, SQLAlchemyError, ValueError) as exc:
                    logger.exception('Could not register MinIO connection.')
                    connection_error = str(exc)
                else:
                    _queue_feedback(
                        event_type='minio_provider_registered',
                        status='success',
                        title='MinIO Connection Registered',
                        message=f'{instance.name} is registered as a reusable MinIO Object Storage connection.',
                        detail='Run Core Validation, then add Prometheus metrics or Alertmanager alert consumer bindings only when required.',
                        action_url=url_for('minio.instance_detail', instance_id=instance.id),
                    )
                    return redirect(url_for('minio.instance_detail', instance_id=instance.id))

    return render_template(
        'minio/instance_form.html',
        form=form,
        registration_proof=registration_proof,
        connection_result=connection_result,
        connection_error=connection_error,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@minio_bp.post('/instances/test-connection')
@permission_required('settings.manage_integrations')
def test_new_instance_connection() -> ResponseReturnValue:
    form = MinioInstanceForm()
    connected = False
    registration_proof = ''

    if not form.validate_on_submit():
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='minio_connection_test_failed',
            status='error',
            title='MinIO connection test failed',
            message='Review the submitted MinIO connection fields before testing this source.',
            detail='The submitted form did not satisfy the MinIO connection contract.',
            action_url=url_for('minio.new_instance'),
            action_label='Review MinIO form',
            action_icon='database',
            metadata={'fields': sorted(form.errors), 'draft_connection': True},
            queue_feedback=False,
        )
    else:
        values = form.to_input()
        try:
            result = test_minio_connection(values)
        except (MinioConnectionError, ValueError) as exc:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='minio_connection_test_failed',
                status='error',
                title='MinIO connection test failed',
                message=str(exc),
                detail='Review the MinIO S3 API endpoint, credentials, TLS trust, and required read-only discovery permissions.',
                action_url=url_for('minio.new_instance'),
                action_label='Review MinIO form',
                action_icon='database',
                metadata={'draft_connection': True, 'submitted_name': values.name},
                queue_feedback=False,
            )
        else:
            connected = True
            registration_proof = issue_registration_proof(values=values, user_id=int(current_user.id))
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='minio_connection_test',
                status='success',
                title='MinIO connection verified',
                message='KAORI reached the submitted MinIO S3 API endpoint.',
                detail=(
                    f'MinIO S3 API returned {result.bucket_count} visible bucket(s) in {result.latency_ms} ms. '
                    + (
                        f'Product identity evidence: {result.identity_evidence}. '
                        if result.product == 'minio'
                        else 'AStor product family was detected; Core Validation will apply its own compatibility qualification. '
                        if result.product == 'astor'
                        else 'Product identity was not conclusive during Test Connection and will be resolved by Core Validation. '
                    )
                    + 'Register the connection, then run Core Validation.'
                ),
                action_url=url_for('minio.new_instance'),
                action_label='Review MinIO form',
                action_icon='database',
                metadata={
                    'draft_connection': True,
                    'submitted_name': values.name,
                    'bucket_count': result.bucket_count,
                    'latency_ms': result.latency_ms,
                    'deployment_id': result.deployment_id,
                    'detected_product': result.product,
                },
                queue_feedback=False,
            )

    response = make_response(
        render_template(
            'minio/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {
            'minio-connection-tested': {
                'connected': connected,
                'proof': registration_proof,
            }
        },
        separators=(',', ':'),
    )
    return response


@minio_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def edit_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = MinioInstanceForm(obj=instance, existing_instance=instance)
    if request.method == 'GET':
        form.secret_key.data = ''

    if form.validate_on_submit():
        try:
            updated = update_minio_instance(instance, form.to_input(existing_instance=instance))
        except (CredentialEncryptionError, SQLAlchemyError, ValueError) as exc:
            logger.exception('Could not update MinIO connection %s.', instance_id)
            _queue_feedback(
                event_type='minio_provider_update_failed',
                status='error',
                title='MinIO Connection Not Updated',
                message=f'KAORI could not update {instance.name}.',
                detail=str(exc),
                action_url=url_for('minio.edit_instance', instance_id=instance.id),
            )
        else:
            _queue_feedback(
                event_type='minio_provider_updated',
                status='success',
                title='MinIO Connection Updated',
                message=f'{updated.name} configuration was saved.',
                detail='Connection-sensitive changes reset provider readiness. Run Core Validation before using the updated MinIO connection operationally.',
                action_url=url_for('minio.index', tab='registry'),
            )
            return redirect(url_for('minio.index', tab='registry'))

    return render_template(
        'minio/instance_form.html',
        form=form,
        instance=instance,
        registration_proof='',
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@minio_bp.post('/instances/<int:instance_id>/test-configuration')
@permission_required('settings.manage_integrations')
def test_instance_configuration(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = MinioInstanceForm(existing_instance=instance)
    if not form.validate_on_submit():
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='minio_configuration_test_failed',
            status='error',
            title='MinIO configuration test failed',
            message='Review the submitted MinIO connection fields before testing this configuration.',
            detail='The submitted form did not satisfy the MinIO connection contract.',
            action_url=url_for('minio.edit_instance', instance_id=instance.id),
            action_label='Review MinIO configuration',
            action_icon='settings-2',
            metadata={'fields': sorted(form.errors), 'instance_id': instance.id},
            queue_feedback=False,
        )
    else:
        values = form.to_input(existing_instance=instance)
        try:
            result = test_minio_connection(values)
        except (MinioConnectionError, ValueError) as exc:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='minio_configuration_test_failed',
                status='error',
                title='MinIO configuration test failed',
                message=str(exc),
                detail='Review the MinIO S3 API endpoint, credentials, TLS trust, and required read-only discovery permissions.',
                action_url=url_for('minio.edit_instance', instance_id=instance.id),
                action_label='Review MinIO configuration',
                action_icon='settings-2',
                metadata={'instance_id': instance.id},
                queue_feedback=False,
            )
        else:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='minio_configuration_test',
                status='success',
                title='MinIO configuration reachable',
                message='KAORI reached the submitted MinIO S3 API endpoint with the effective credential.',
                detail=f'S3 API returned {result.bucket_count} visible bucket(s) in {result.latency_ms} ms. Save changes, then run Core Validation.',
                action_url=url_for('minio.edit_instance', instance_id=instance.id),
                action_label='Review MinIO configuration',
                action_icon='settings-2',
                metadata={
                    'instance_id': instance.id,
                    'bucket_count': result.bucket_count,
                    'latency_ms': result.latency_ms,
                },
                queue_feedback=False,
            )
    return render_template(
        'minio/partials/_connection_test_result.html',
        connection_feedback=feedback,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@minio_bp.get('/instances/<int:instance_id>')
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    validation_task_id = get_active_validation_task_id(
        provider_type='minio',
        operation='full_validation',
        instance_id=instance.id,
    )
    runtime_task_id = get_active_validation_task_id(
        provider_type='minio',
        operation='runtime_refresh',
        instance_id=instance.id,
    )

    return render_template(
        'minio/instance_detail.html',
        **build_detail_context(instance, detail_query_from_request()),
        validation_job=build_validation_snapshot(validation_task_id) if validation_task_id else None,
        runtime_refresh_job=build_validation_snapshot(runtime_task_id) if runtime_task_id else None,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@minio_bp.get('/instances/<int:instance_id>/capabilities/registry')
@permission_required('settings.manage_integrations')
def capability_registry(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    context = build_detail_context(instance, detail_query_from_request())
    validation_task_id = get_active_validation_task_id(
        provider_type='minio',
        operation='full_validation',
        instance_id=instance.id,
    )
    context['validation_job'] = build_validation_snapshot(validation_task_id) if validation_task_id else None
    return render_template('minio/partials/_capability_registry.html', **context)


@minio_bp.post('/instances/<int:instance_id>/validate')
@permission_required('settings.manage_integrations')
def validate_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    validation_job, feedback = queue_full_validation(
        instance,
        user_id=int(current_user.id),
        is_htmx=is_htmx,
    )
    if is_htmx:
        context = build_detail_context(instance, detail_query_from_request())
        context.update(validation_job=validation_job, operation_feedback=feedback)
        return render_template('minio/partials/_detail_validation.html', **context)
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='validation'))


@minio_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('settings.manage_integrations')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    runtime_refresh_job, feedback = queue_runtime_refresh(
        instance,
        user_id=int(current_user.id),
        is_htmx=is_htmx,
    )
    if is_htmx:
        context = build_detail_context(instance, detail_query_from_request())
        context.update(
            runtime_refresh_job=runtime_refresh_job,
            operation_feedback=feedback,
            runtime_history_oob=True,
        )
        return render_template('minio/partials/_detail_runtime.html', **context)
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='runtime'))


@minio_bp.get('/instances/<int:instance_id>/runtime/refresh/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def runtime_refresh_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(snapshot, provider_type='minio', instance_id=instance.id):
        abort(404)
    context = build_detail_context(instance)
    context.update(
        runtime_refresh_job=snapshot,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        runtime_history_oob=True,
    )
    return render_template('minio/partials/_detail_runtime.html', **context)


@minio_bp.get('/instances/<int:instance_id>/validation/status/<string:task_id>')
@permission_required('settings.manage_integrations')
def validation_status(instance_id: int, task_id: str) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(snapshot, provider_type='minio', instance_id=instance.id):
        abort(404)
    context = build_detail_context(instance, detail_query_from_request())
    context.update(
        validation_job=snapshot,
        operation_feedback=snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
    )
    return render_template('minio/partials/_detail_validation.html', **context)


@minio_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('settings.manage_integrations')
def runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    context = build_detail_context(instance, detail_query_from_request())
    return render_template(
        'integrations/partials/_runtime_history.html',
        runtime_history=context['runtime_history'],
        runtime_history_id='minio-runtime-history',
        runtime_history_loading_id='minio-history-loading',
        runtime_history_url=url_for('minio.runtime_history', instance_id=instance.id),
        runtime_history_endpoint='minio.runtime_history',
        runtime_history_route_args={'instance_id': instance.id},
        runtime_history_detail_url=url_for('minio.instance_detail', instance_id=instance.id),
        runtime_history_detail_endpoint='minio.instance_detail',
        runtime_history_filters_enabled=True,
        provider_label='MinIO',
    )


@minio_bp.get('/instances/<int:instance_id>/bindings/registry')
@permission_required('settings.manage_integrations')
def binding_registry(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    return render_template(
        'minio/partials/_binding_registry.html',
        **build_detail_context(instance, detail_query_from_request()),
    )


@minio_bp.post('/instances/<int:instance_id>/delete')
@permission_required('settings.manage_integrations')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    instance_name = instance.name
    asset_name = instance.object_storage_system.name
    try:
        summary = delete_minio_instance(instance)
    except DeletionBlocked as exc:
        logger.warning('MinIO deletion blocked for %s: %s', instance_id, exc)
        _queue_feedback(
            event_type='minio_instance_delete_rejected',
            status='warning',
            title='MinIO Connection Deletion Blocked',
            message=f'{instance_name} still has active operational dependencies.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance_id, _anchor='scope'),
        )
        return redirect(url_for('minio.instance_detail', instance_id=instance_id, _anchor='scope'))
    except SQLAlchemyError:
        logger.exception('MinIO instance deletion failed for %s.', instance_id)
        _queue_feedback(
            event_type='minio_instance_delete_failed',
            status='error',
            title='MinIO Connection Not Deleted',
            message=f'KAORI could not delete {instance_name}.',
            detail='Review database connectivity and dependent records before retrying the deletion.',
            action_url=url_for('minio.instance_detail', instance_id=instance_id, _anchor='scope'),
        )
        return redirect(url_for('minio.instance_detail', instance_id=instance_id, _anchor='scope'))

    record_operational_activity(
        user_id=int(current_user.id),
        event_type='minio_instance_deleted',
        status='success',
        title='MinIO Connection Deleted',
        message=f'{instance_name} and its object-storage asset were removed from KAORI.',
        detail=(
            f'Removed {summary["asset_bindings"]} asset-scoped binding(s) for {asset_name}. '
            'Reusable Prometheus and Alertmanager source connections remain registered; runtime history and Activity Audit evidence are retained.'
        ),
        action_url=url_for('minio.index', tab='registry'),
        action_label='Open MinIO Registry',
        action_icon='database',
        metadata={'instance_name': instance_name, 'asset_name': asset_name, **summary},
        queue_feedback=True,
    )
    return redirect(url_for('minio.index', tab='registry'))
