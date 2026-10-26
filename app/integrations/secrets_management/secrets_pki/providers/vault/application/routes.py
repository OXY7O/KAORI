from __future__ import annotations

import logging
from dataclasses import replace

from celery.exceptions import CeleryError
from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.common.pagination import paginate_query
from app.integrations.secrets_management.secrets_pki.inventory_presentation import vault_inventory_readiness
from app.integrations.secrets_management.secrets_pki.providers.vault.application.forms import VaultConnectionForm
from app.integrations.secrets_management.secrets_pki.providers.vault.application.registration import issue_proof, verified_secret
from app.integrations.secrets_management.secrets_pki.providers.vault.application.service import save_connection, test_connection
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultProviderError
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import enqueue_instance_validation, enqueue_runtime_health_refresh
from app.kubernetes.cluster.constants import ENVIRONMENTS
from app.models.integration import IntegrationInstance
from app.models.runtime import IntegrationRuntimeObservation
from app.models.vault import VaultInstance
from app.platform_operations.notifications.service import get_navigation_notification_context, record_operational_activity
from app.security.credentials import CredentialEncryptionError
from app.secrets_pki.pki_presentation import pki_public_readiness
from app.secrets_pki.pki_stored_presentation import stored_pki_certificate_readiness

logger = logging.getLogger(__name__)
vault_bp = Blueprint('vault', __name__, url_prefix='/integrations/secrets-management/secrets-pki/vault')


def _instance_or_404(instance_id: int) -> VaultInstance:
    instance = VaultInstance.query.filter_by(id=instance_id).first()
    if instance is None:
        abort(404)
    return instance


def _notification() -> dict:
    return get_navigation_notification_context(user_id=int(current_user.id))


def _evidence(instance: VaultInstance) -> dict:
    validation_id = get_active_validation_task_id(
        integration_type='secrets_pki', operation='full_validation',
        integration_instance_id=instance.integration_instance_id,
    )
    runtime_id = get_active_validation_task_id(
        integration_type='secrets_pki', operation='runtime_refresh',
        integration_instance_id=instance.integration_instance_id,
    )
    return {
        'validation_job': build_validation_snapshot(validation_id) if validation_id else None,
        'runtime_job': build_validation_snapshot(runtime_id) if runtime_id else None,
    }


@vault_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    query = VaultInstance.query.join(VaultInstance.integration_instance).order_by(VaultInstance.id.asc())
    registered = query.count()
    search = request.args.get('q', '').strip()[:80]
    environment = request.args.get('environment', '').strip()
    readiness_filter = request.args.get('readiness', '').strip()
    valid_environments = {value for value, _label in ENVIRONMENTS}
    if environment not in valid_environments:
        environment = ''
    if readiness_filter not in {'ready', 'validation_required', 'blocked', 'degraded'}:
        readiness_filter = ''
    filtered = query
    if search:
        filtered = filtered.filter(
            IntegrationInstance.name.icontains(search, autoescape=True)
            | VaultInstance.endpoint.icontains(search, autoescape=True)
        )
    if environment:
        filtered = filtered.filter(IntegrationInstance.environment == environment)
    if readiness_filter:
        filtered = filtered.filter(IntegrationInstance.readiness_status == readiness_filter)
    instances, pagination = paginate_query(
        filtered, page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    enabled = query.filter(
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.lifecycle_status == 'active',
    ).count()
    ready = query.filter(
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.lifecycle_status == 'active',
        IntegrationInstance.readiness_status == 'ready',
    ).count()
    tab = str(request.args.get('tab', 'coverage')).strip().lower()
    return render_template(
        'integrations/secrets_management/vault/index.html',
        instances=instances,
        pagination=pagination,
        registered=registered,
        ready=ready,
        attention=max(0, enabled - ready),
        disabled=max(0, registered - enabled),
        active_tab=tab if tab in {'coverage', 'registry'} else 'coverage',
        registry_search=search,
        registry_environment=environment,
        registry_readiness=readiness_filter,
        environment_options=ENVIRONMENTS,
        notification_context=_notification(),
    )


@vault_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def new_instance() -> ResponseReturnValue:
    form = VaultConnectionForm()
    message = None
    proof = request.form.get('connection_test_proof', '')
    if form.validate_on_submit():
        values = form.to_input()
        action = str(request.form.get('action') or 'save')
        if action == 'test':
            try:
                test_connection(values)
                proof = issue_proof(values, int(current_user.id))
                message = 'Vault identity and AppRole token lookup verified. Save then run Full Validation.'
            except (VaultProviderError, ValueError, CredentialEncryptionError) as exc:
                message = str(exc)
                proof = ''
        elif action == 'save':
            try:
                credential = verified_secret(proof, values, int(current_user.id))
            except CredentialEncryptionError:
                credential = None
            if credential is None:
                message = 'Test this exact connection successfully before saving.'
            else:
                try:
                    instance = save_connection(replace(values, secret_id=credential))
                except (SQLAlchemyError, CredentialEncryptionError, ValueError):
                    logger.exception('Vault registration failed.')
                    message = 'Vault registration failed; review endpoint, encryption key and connection name.'
                else:
                    record_operational_activity(
                        user_id=int(current_user.id), event_type='vault_connection_registered',
                        status='success', title='Vault Connection Registered',
                        message='A Vault AppRole integration connection was registered.',
                        detail='Test Connection is not Full Validation; run provider validation next.',
                        action_url=url_for('vault.detail', instance_id=instance.id),
                        queue_feedback=True,
                    )
                    return redirect(url_for('vault.detail', instance_id=instance.id))
    return render_template(
        'integrations/secrets_management/vault/form.html',
        form=form, proof=proof, instance=None, message=message, notification_context=_notification(),
    )


@vault_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def edit_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = VaultConnectionForm(existing=instance, obj=instance)
    proof = request.form.get('connection_test_proof', '')
    message = None
    if form.validate_on_submit():
        values = form.to_input()
        action = str(request.form.get('action') or 'save')
        if action == 'test':
            try:
                test_connection(values)
                proof = issue_proof(values, int(current_user.id))
                message = 'Connection verified. Save the configuration to apply changes.'
            except (VaultProviderError, ValueError, CredentialEncryptionError) as exc:
                proof = ''
                message = str(exc)
        elif action == 'save':
            try:
                credential = verified_secret(proof, values, int(current_user.id))
            except CredentialEncryptionError:
                credential = None
            if credential is None:
                message = 'Test this exact configuration successfully before saving.'
            else:
                try:
                    save_connection(replace(values, secret_id=credential), existing=instance)
                except (SQLAlchemyError, CredentialEncryptionError, ValueError):
                    logger.exception('Vault configuration update failed.')
                    message = 'Could not save Vault configuration; review the required encryption key.'
                else:
                    record_operational_activity(
                        user_id=int(current_user.id), event_type='vault_connection_updated',
                        status='success', title='Vault Connection Updated',
                        message='Vault connection configuration was saved.',
                        detail='Changed authentication or endpoint fields require a fresh Full Validation.',
                        action_url=url_for('vault.detail', instance_id=instance.id),
                        queue_feedback=True,
                    )
                    return redirect(url_for('vault.detail', instance_id=instance.id))
    return render_template(
        'integrations/secrets_management/vault/form.html', form=form, instance=instance,
        proof=proof, message=message, notification_context=_notification(),
    )


@vault_bp.get('/instances/<int:instance_id>')
@permission_required('integrations.manage')
def detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    history, history_pagination = paginate_runtime_history(
        'secrets_pki', str(instance.id),
        page=request.args.get('history_page', 1, type=int) or 1,
        per_page=request.args.get('history_per_page', 5, type=int) or 5,
    )
    latest_runtime_observation = (
        IntegrationRuntimeObservation.query.filter_by(
            integration_type='secrets_pki',
            instance_id=str(instance.id),
        )
        .order_by(IntegrationRuntimeObservation.observed_at.desc(), IntegrationRuntimeObservation.id.desc())
        .first()
    )
    return render_template(
        'integrations/secrets_management/vault/detail.html',
        instance=instance, evidence=_evidence(instance),
        latest_runtime_observation=latest_runtime_observation,
        inventory_readiness=vault_inventory_readiness(instance),
        public_pki_readiness=pki_public_readiness(instance=instance),
        stored_cert_readiness=stored_pki_certificate_readiness(instance=instance),
        runtime_history=history, runtime_history_pagination=history_pagination,
        can_view_secrets_pki=current_user.has_permission('secrets_pki.view'),
        can_view_cert_analytics=(current_user.has_permission('secrets_pki.view')
                                 and current_user.has_permission('analytics.view')),
        notification_context=_notification(),
    )


@vault_bp.post('/instances/<int:instance_id>/validate')
@permission_required('integrations.manage')
def validate(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    if not instance.enabled:
        abort(409)
    try:
        enqueue_instance_validation(
            integration_type='secrets_pki', integration_instance_id=instance.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError):
        logger.exception('Vault validation could not be queued.')
        record_operational_activity(
            user_id=int(current_user.id), event_type='vault_validation_queue_failed',
            status='error', title='Vault Validation Not Queued',
            message='Verify Redis and the integration-validation worker.',
            detail='No Vault Full Validation job was admitted.',
            action_url=url_for('vault.detail', instance_id=instance.id),
            queue_feedback=True,
        )
    return redirect(url_for('vault.detail', instance_id=instance.id, _anchor='validation'))


@vault_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('integrations.manage')
def runtime_refresh(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    if not instance.enabled:
        abort(409)
    try:
        enqueue_runtime_health_refresh(
            integration_type='secrets_pki', integration_instance_id=instance.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError):
        logger.exception('Vault runtime refresh could not be queued.')
        record_operational_activity(
            user_id=int(current_user.id), event_type='vault_runtime_queue_failed',
            status='error', title='Vault Runtime Refresh Not Queued',
            message='Verify Redis and the integration-runtime worker.',
            detail='No Vault runtime refresh job was admitted.',
            action_url=url_for('vault.detail', instance_id=instance.id),
            queue_feedback=True,
        )
    return redirect(url_for('vault.detail', instance_id=instance.id, _anchor='runtime'))
