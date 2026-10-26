"""GitHub Source Control Dev Container review workspace (#2742).

Intentional privilege boundary: only admitted GitHub provider and local super-admin
until KAORI #724 supplies native resource-scoped installation authorization.
No API calls during GET; committed KAORI state is the only read source.
"""

from __future__ import annotations

import json

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import or_

from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.integrations.source_control.repository_inventory import read_installation_inventory
from app.integrations.source_control.source_control.providers.github.application.forms import (
    GitHubAppConnectionEditForm,
)
from app.integrations.source_control.source_control.providers.github.application.registration_proof import (
    issue_github_registration_proof,
    verify_github_registration_proof,
)
from app.integrations.source_control.source_control.providers.github.job_admission import (
    enqueue_github_app_job,
)
from app.integrations.source_control.source_control.providers.github.registration import (
    build_edit_connection_input,
    test_connection,
    update_github_connection_configuration,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.integrations.source_control.sync_jobs import (
    NoEligibleSourceControlTargets,
    enqueue_source_repository_sync,
)
from app.integrations.source_control.uat_access import require_uat_access
from app.models.job import JobExecution
from app.models.source_control import SourceInstallation, SourceWebhookDelivery
from app.platform_operations.notifications.service import record_operational_activity
from app.security.credentials import CredentialEncryptionError
from sqlalchemy.exc import SQLAlchemyError

github_uat_bp = Blueprint(
    'github_source_uat', __name__, url_prefix='/integrations/source-control/github/uat',
)


def _response(name: str, **context) -> ResponseReturnValue:
    response = make_response(render_template(name, **context))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


def _installation_or_404(installation_id: int) -> SourceInstallation:
    require_uat_access()
    record = db.session.get(SourceInstallation, installation_id)
    if record is None or record.provider_key != 'github' or record.host_key != 'github.com':
        abort(404)
    return record


def _inventory_context(installation: SourceInstallation) -> dict:
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    per_page = request.args.get('per_page', 5, type=int) or 5
    if per_page not in (5, 10, 25, 50):
        per_page = 5
    inventory = read_installation_inventory(
        db.session, authorized_installation_id=installation.id,
        page=page, per_page=per_page,
    )
    return {'inventory': inventory, 'installation': installation}


@github_uat_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    require_uat_access()
    records = (
        SourceInstallation.query
        .filter_by(provider_key='github', host_key='github.com')
        .order_by(SourceInstallation.id)
        .limit(50)
        .all()
    )
    return _response(
        'integrations/source_control/github/uat_index.html',
        installations=records,
    )


@github_uat_bp.get('/installations/<int:installation_id>')
@permission_required('integrations.manage')
def detail(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    canonical = installation.integration_instance
    jobs = (
        JobExecution.query
        .filter(or_(
            JobExecution.integration_instance_id == installation.integration_instance_id,
            JobExecution.scope_key == f'installation:{installation.id}',
        ))
        .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
        .limit(5)
        .all()
    )
    return _response(
        'integrations/source_control/github/uat_detail.html',
        **_inventory_context(installation),
        canonical=canonical, jobs=jobs, deliveries=(
            SourceWebhookDelivery.query.filter_by(installation_id=installation.id)
            .order_by(SourceWebhookDelivery.received_at.desc()).limit(5).all()
        ), action_form=FlaskForm(),
        feedback=request.args.get('feedback', ''),
    )


@github_uat_bp.route('/installations/<int:installation_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def edit_connection(installation_id: int) -> ResponseReturnValue:
    """Guarded edit and tested credential rotation; never rehydrate secrets."""
    installation = _installation_or_404(installation_id)
    canonical = installation.integration_instance
    if canonical is None:
        abort(409)
    form = GitHubAppConnectionEditForm(obj=canonical) if request.method == 'GET' else GitHubAppConnectionEditForm()
    action = str(request.form.get('action') or '').strip() if request.method == 'POST' else ''
    inline_test = request.headers.get('HX-Request') == 'true' and action == 'test'
    message = None
    test_proof = None
    rejection = False

    if request.method == 'POST' and action not in {'test', 'save'}:
        abort(400)
    if form.validate_on_submit():
        replacement_pem = str(form.private_key_pem.data or '')
        replacement_webhook = str(form.webhook_secret.data or '')
        replacement_requested = bool(replacement_pem or replacement_webhook)
        name = str(form.name.data or '').strip()
        environment = str(form.environment.data or '').strip()
        description = str(form.description.data or '').strip() or None
        enabled = bool(form.enabled.data)
        try:
            if action == 'test':
                values = build_edit_connection_input(
                    installation,
                    name=name,
                    environment=environment,
                    description=description,
                    enabled=enabled,
                    replacement_private_key_pem=replacement_pem,
                    replacement_webhook_secret=replacement_webhook,
                )
                test_connection(values)
                test_proof = issue_github_registration_proof(
                    user_id=int(current_user.id),
                    values=values,
                )
                message = 'GitHub App installation verified. Webhook secret validity is not tested by this API.'
            else:
                if replacement_requested:
                    values = build_edit_connection_input(
                        installation,
                        name=name,
                        environment=environment,
                        description=description,
                        enabled=enabled,
                        replacement_private_key_pem=replacement_pem,
                        replacement_webhook_secret=replacement_webhook,
                    )
                    valid, reason = verify_github_registration_proof(
                        token=str(request.form.get('connection_test_proof') or '').strip(),
                        user_id=int(current_user.id),
                        values=values,
                    )
                    if not valid:
                        message = reason
                        rejection = True
                if not rejection:
                    invalidated = update_github_connection_configuration(
                        installation,
                        name=name,
                        environment=environment,
                        description=description,
                        enabled=enabled,
                        replacement_private_key_pem=replacement_pem,
                        replacement_webhook_secret=replacement_webhook,
                    )
                    record_operational_activity(
                        user_id=int(current_user.id),
                        event_type='source_control_connection_updated',
                        status='success',
                        title='GitHub Connection Updated',
                        message='Canonical GitHub connection configuration was updated.',
                        detail=(
                            'Configuration changed; run Full Validation before operational use.'
                            if invalidated
                            else 'Descriptive settings saved; existing validation evidence retained.'
                        ),
                        action_url=url_for('github_source_uat.detail', installation_id=installation.id),
                        metadata={
                            'installation_id': installation.id,
                            'integration_instance_id': canonical.id,
                            'readiness_invalidated': invalidated,
                            'shared_app_credential_rotation': replacement_requested,
                        },
                        queue_feedback=True,
                    )
                    return redirect(
                        url_for(
                            'github_source_uat.detail',
                            installation_id=installation.id,
                            feedback=(
                                'configuration_revalidation_required' if invalidated else 'configuration_updated'
                            ),
                        )
                    )
        except (ValueError, GitHubProviderError, CredentialEncryptionError):
            message = 'GitHub connection could not be verified. Check configuration and replacement credentials.'
            rejection = True
        except SQLAlchemyError:
            message = 'GitHub configuration could not be saved. Review the connection settings.'
            rejection = True
        finally:
            form.clear_sensitive_fields()
    elif request.method == 'POST':
        message = 'Review the highlighted fields and try again.'
        rejection = True
        form.clear_sensitive_fields()

    if inline_test:
        response = _response(
            'integrations/source_control/github/partials/_connection_test_result.html',
            verified=bool(test_proof),
            message=message,
        )
        if test_proof:
            response.headers['HX-Trigger'] = json.dumps(
                {'github-connection-tested': {'connected': True, 'proof': test_proof}}
            )
        return response

    response = _response(
        'integrations/source_control/github/edit.html',
        installation=installation,
        canonical=canonical,
        form=form,
        message=message,
    )
    if rejection and request.method == 'POST' and form.errors == {}:
        response.status_code = 409
    return response


@github_uat_bp.get('/installations/<int:installation_id>/inventory')
@permission_required('integrations.manage')
def inventory_table(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    context = _inventory_context(installation)
    if request.headers.get('HX-Request') != 'true':
        return redirect(url_for('github_source_uat.detail', installation_id=installation_id,
                                **request.args))
    return _response('integrations/source_control/github/_inventory_table.html', **context)


@github_uat_bp.post('/installations/<int:installation_id>/validate')
@permission_required('integrations.manage')
def validate(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    try:
        enqueue_github_app_job(
            installation, operation='full_validation',
            requested_by_user_id=int(current_user.id),
        )
    except (GitHubProviderError, RuntimeError, ValueError):
        return redirect(url_for('github_source_uat.detail', installation_id=installation_id,
                                feedback='validation_blocked'))
    return redirect(url_for('github_source_uat.detail', installation_id=installation_id,
                            feedback='validation_queued'))


@github_uat_bp.post('/installations/<int:installation_id>/sync')
@permission_required('integrations.manage')
def synchronize(installation_id: int) -> ResponseReturnValue:
    _installation_or_404(installation_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    try:
        enqueue_source_repository_sync(
            requested_by_user_id=int(current_user.id),
            trigger_type='uat',
            installation_record_id=installation_id,
        )
    except (NoEligibleSourceControlTargets, RuntimeError, ValueError):
        return redirect(url_for('github_source_uat.detail', installation_id=installation_id,
                                feedback='sync_blocked'))
    return redirect(url_for('github_source_uat.detail', installation_id=installation_id,
                            feedback='sync_queued'))
