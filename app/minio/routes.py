from __future__ import annotations

import logging

from celery.exceptions import CeleryError
from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.minio.client import MinioConnectionError
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    enqueue_binding_validation,
    enqueue_instance_validation,
)
from app.minio.forms import MinioAlertBindingForm, MinioInstanceForm, MinioMetricsBindingForm
from app.minio.presentation import build_detail_context, build_index_context
from app.minio.registration import issue_registration_proof, verify_registration_proof
from app.minio.service import (
    alert_source_for_binding,
    alertmanager_choices,
    bind_alertmanager_alerts,
    bind_prometheus_metrics,
    create_minio_instance,
    current_alert_binding,
    current_metrics_binding,
    metrics_source_for_binding,
    prometheus_choices,
    remove_alert_binding,
    remove_metrics_binding,
    test_minio_connection,
)
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
    return render_template(
        'minio/index.html',
        **build_index_context(
            tab=request.args.get('tab', 'coverage').strip(),
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
            coverage_page=request.args.get('coverage_page', 1, type=int) or 1,
            coverage_per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
        ),
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


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


@minio_bp.get('/instances/<int:instance_id>')
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding_form = MinioMetricsBindingForm()
    binding_form.prometheus_instance_id.choices = prometheus_choices()
    alert_binding_form = MinioAlertBindingForm()
    alert_binding_form.alertmanager_instance_id.choices = alertmanager_choices()

    validation_task_id = get_active_validation_task_id(
        provider_type='minio',
        operation='full_validation',
        instance_id=instance.id,
    )
    metrics_binding = current_metrics_binding(instance)
    metrics_source = metrics_source_for_binding(metrics_binding)
    binding_job = None
    if metrics_binding is not None and metrics_source is not None:
        binding_task_id = get_active_validation_task_id(
            provider_type='prometheus',
            operation='binding_validation',
            instance_id=metrics_source.id,
            binding_id=metrics_binding.id,
        )
        if binding_task_id:
            binding_job = build_validation_snapshot(binding_task_id)

    alert_binding = current_alert_binding(instance)
    alert_source = alert_source_for_binding(alert_binding)
    alert_binding_job = None
    if alert_binding is not None and alert_source is not None:
        alert_task_id = get_active_validation_task_id(
            provider_type='alertmanager',
            operation='binding_validation',
            instance_id=alert_source.id,
            binding_id=alert_binding.id,
        )
        if alert_task_id:
            alert_binding_job = build_validation_snapshot(alert_task_id)

    return render_template(
        'minio/instance_detail.html',
        **build_detail_context(instance),
        binding_form=binding_form,
        alert_binding_form=alert_binding_form,
        validation_job=build_validation_snapshot(validation_task_id) if validation_task_id else None,
        binding_validation_job=binding_job,
        alert_binding_validation_job=alert_binding_job,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@minio_bp.post('/instances/<int:instance_id>/validate')
@permission_required('settings.manage_integrations')
def validate_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    try:
        _snapshot, created = enqueue_instance_validation(
            provider_type='minio',
            instance_id=instance.id,
            requested_by_user_id=int(current_user.id),
        )
        _queue_feedback(
            event_type='minio_validation_queued',
            status='info',
            title='MinIO Validation Queued',
            message=f'KAORI queued Full Validation for {instance.name}.',
            detail='The worker will refresh S3 API, compatibility, capability, and canonical asset-binding evidence.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='validation'),
        )
        if not created:
            logger.info('Reused active MinIO validation job for instance %s.', instance.id)
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        logger.exception('Could not queue MinIO validation.')
        _queue_feedback(
            event_type='minio_validation_queue_failed',
            status='error',
            title='MinIO Validation Could Not Start',
            message=f'KAORI could not queue Full Validation for {instance.name}.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance.id),
        )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='validation'))


@minio_bp.post('/instances/<int:instance_id>/metrics-binding')
@permission_required('settings.manage_integrations')
def create_metrics_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = MinioMetricsBindingForm()
    form.prometheus_instance_id.choices = prometheus_choices()
    if not form.validate_on_submit():
        detail = '; '.join(error for errors in form.errors.values() for error in errors) or 'Review binding fields.'
        _queue_feedback(
            event_type='minio_metrics_binding_invalid',
            status='error',
            title='Metrics Binding Not Saved',
            message='The Prometheus binding request is incomplete.',
            detail=detail,
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
        return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))

    try:
        binding = bind_prometheus_metrics(instance, form.to_input())
        source = metrics_source_for_binding(binding)
        if source is None:
            raise RuntimeError('The selected Prometheus source could not be resolved after binding creation.')
        enqueue_binding_validation(
            provider_type='prometheus',
            instance_id=source.id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        _queue_feedback(
            event_type='minio_metrics_binding_created',
            status='success',
            title='MinIO Metrics Binding Saved',
            message=f'{source.name} is now bound to {instance.object_storage_system.name}.',
            detail='KAORI queued validation of the MinIO metrics selector against the registered object-storage profile.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        logger.exception('Could not create MinIO Prometheus binding.')
        _queue_feedback(
            event_type='minio_metrics_binding_failed',
            status='error',
            title='MinIO Metrics Binding Failed',
            message='KAORI could not bind this object-storage asset to Prometheus.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))


@minio_bp.post('/instances/<int:instance_id>/metrics-binding/validate')
@permission_required('settings.manage_integrations')
def validate_metrics_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = current_metrics_binding(instance)
    source = metrics_source_for_binding(binding)
    if binding is None or source is None:
        _queue_feedback(
            event_type='minio_metrics_binding_missing',
            status='warning',
            title='Metrics Binding Not Configured',
            message='Bind a Prometheus source before validating MinIO metrics.',
            detail='The metrics plane is independent from the MinIO S3 API connection.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
        return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))
    try:
        enqueue_binding_validation(
            provider_type='prometheus',
            instance_id=source.id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        _queue_feedback(
            event_type='minio_metrics_binding_validation_queued',
            status='info',
            title='MinIO Metrics Validation Queued',
            message=f'KAORI queued selector validation through {source.name}.',
            detail='Validation probes MinIO software identity, cluster usage, and bucket usage metrics within the bound selector.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        _queue_feedback(
            event_type='minio_metrics_binding_validation_failed',
            status='error',
            title='MinIO Metrics Validation Could Not Start',
            message='KAORI could not queue the Prometheus binding validation.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))


@minio_bp.post('/instances/<int:instance_id>/metrics-binding/remove')
@permission_required('settings.manage_integrations')
def delete_metrics_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    removed = remove_metrics_binding(instance)
    _queue_feedback(
        event_type='minio_metrics_binding_removed',
        status='success' if removed else 'info',
        title='MinIO Metrics Binding Removed' if removed else 'No Metrics Binding Changed',
        message=(
            f'Prometheus is no longer bound to {instance.object_storage_system.name}.'
            if removed
            else 'This object-storage asset did not have an active Prometheus binding.'
        ),
        detail='MinIO API registration remains unchanged.',
        action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
    )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))


@minio_bp.post('/instances/<int:instance_id>/alert-binding')
@permission_required('settings.manage_integrations')
def create_alert_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = MinioAlertBindingForm()
    form.alertmanager_instance_id.choices = alertmanager_choices()
    if not form.validate_on_submit():
        detail = '; '.join(error for errors in form.errors.values() for error in errors) or 'Review binding fields.'
        _queue_feedback(
            event_type='minio_alert_binding_invalid',
            status='error',
            title='Alert Binding Not Saved',
            message='The Alertmanager binding request is incomplete.',
            detail=detail,
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
        return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))

    try:
        binding = bind_alertmanager_alerts(instance, form.to_input())
        source = alert_source_for_binding(binding)
        if source is None:
            raise RuntimeError('The selected Alertmanager source could not be resolved after binding creation.')
        enqueue_binding_validation(
            provider_type='alertmanager',
            instance_id=source.id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        _queue_feedback(
            event_type='minio_alert_binding_created',
            status='success',
            title='MinIO Alert Binding Saved',
            message=f'{source.name} is now bound to {instance.object_storage_system.name}.',
            detail='KAORI queued MinIO alert consumer-profile validation for the selected alert identity.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        logger.exception('Could not create MinIO Alertmanager binding.')
        _queue_feedback(
            event_type='minio_alert_binding_failed',
            status='error',
            title='MinIO Alert Binding Failed',
            message='KAORI could not bind this object-storage asset to Alertmanager.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))


@minio_bp.post('/instances/<int:instance_id>/alert-binding/validate')
@permission_required('settings.manage_integrations')
def validate_alert_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    binding = current_alert_binding(instance)
    source = alert_source_for_binding(binding)
    if binding is None or source is None:
        _queue_feedback(
            event_type='minio_alert_binding_missing',
            status='warning',
            title='Alert Binding Not Configured',
            message='Bind an Alertmanager source before validating MinIO alert consumption.',
            detail='Alertmanager provider readiness remains independent from this object-storage consumer binding.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
        return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))
    try:
        enqueue_binding_validation(
            provider_type='alertmanager',
            instance_id=source.id,
            binding_id=binding.id,
            requested_by_user_id=int(current_user.id),
        )
        _queue_feedback(
            event_type='minio_alert_binding_validation_queued',
            status='info',
            title='MinIO Alert Validation Queued',
            message=f'KAORI queued MinIO alert consumer validation through {source.name}.',
            detail='Validation applies the minio-alerts-v1 profile to the bound selector without changing Alertmanager core readiness.',
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        _queue_feedback(
            event_type='minio_alert_binding_validation_failed',
            status='error',
            title='MinIO Alert Validation Could Not Start',
            message='KAORI could not queue the Alertmanager consumer validation.',
            detail=str(exc),
            action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
        )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))


@minio_bp.post('/instances/<int:instance_id>/alert-binding/remove')
@permission_required('settings.manage_integrations')
def delete_alert_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    removed = remove_alert_binding(instance)
    _queue_feedback(
        event_type='minio_alert_binding_removed',
        status='success' if removed else 'info',
        title='MinIO Alert Binding Removed' if removed else 'No Alert Binding Changed',
        message=(
            f'Alertmanager is no longer bound to {instance.object_storage_system.name}.'
            if removed
            else 'This object-storage asset did not have an active Alertmanager binding.'
        ),
        detail='MinIO API registration and Prometheus metrics binding remain unchanged.',
        action_url=url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'),
    )
    return redirect(url_for('minio.instance_detail', instance_id=instance.id, _anchor='scope'))
