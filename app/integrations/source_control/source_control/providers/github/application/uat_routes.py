"""GitHub Source Control Dev Container review workspace (#2742).

Intentional privilege boundary: only admitted GitHub provider and local super-admin
until KAORI #724 supplies native resource-scoped installation authorization.
No API calls during GET; committed KAORI state is the only read source.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.integrations.capability_registry import CapabilityStatusFlags, build_capability_registry_view
from app.integrations.deletion import provider_deletion_guard
from app.integrations.source_control.repository_inventory import read_installation_inventory_for_current_session
from app.integrations.source_control.source_control.providers.github.application.capability_presentation import (
    github_capability_context,
)
from app.integrations.source_control.source_control.providers.github.application.forms import (
    GitHubAppConnectionEditForm,
    GitHubInstallationSuccessorForm,
)
from app.integrations.source_control.source_control.providers.github.application.repository import (
    get_github_installation,
    list_github_uat_installations,
    retire_github_connection,
)
from app.integrations.source_control.source_control.providers.github.application.registration_proof import (
    issue_github_registration_proof,
    issue_github_successor_proof,
    verify_github_registration_proof,
    verify_github_successor_proof,
)
from app.integrations.source_control.source_control.providers.github.application.runtime_presentation import (
    _runtime_context,
    _validation_job_for,
)
from app.integrations.source_control.source_control.providers.github.application.runtime_presentation import (
    _runtime_search_pattern as _runtime_search_pattern,
)
from app.integrations.source_control.source_control.providers.github.job_admission import (
    enqueue_github_app_job,
)
from app.integrations.source_control.source_control.providers.github.registration import (
    build_edit_connection_input,
    build_successor_connection_input,
    save_tested_connection,
    test_connection,
    update_github_connection_configuration,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.integrations.source_control.sync_jobs import (
    NoEligibleSourceControlTargets,
    enqueue_source_repository_sync,
)
from app.integrations.source_control.uat_access import require_uat_access
from app.integrations.validation.state import build_validation_snapshot
from app.integrations.validation.web import validate_snapshot_access, validation_poll_response
from app.models.integration import IntegrationInstance
from app.models.source_control import SourceInstallation
from app.platform_operations.notifications.service import record_operational_activity
from app.security.credentials import CredentialEncryptionError

github_uat_bp = Blueprint(
    'github_source_uat',
    __name__,
    url_prefix='/integrations/source-control/github/uat',
)


def _response(name: str, **context) -> Response:
    response = make_response(render_template(name, **context))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


def _detail_url(installation_id: int, **overrides: str) -> str:
    """Keep user-controlled query values as URL data, not url_for options."""
    filters = request.args.to_dict(flat=True)
    filters.update(overrides)
    url = url_for('github_source_uat.detail', installation_id=installation_id)
    query = urlencode(filters)
    return f'{url}?{query}' if query else url


def _installation_or_404(installation_id: int) -> SourceInstallation:
    require_uat_access()
    record = get_github_installation(installation_id)
    if record is None or record.provider_key != 'github' or record.host_key != 'github.com':
        abort(404)
    return record


def _inventory_context(installation: SourceInstallation) -> dict:
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    per_page = request.args.get('per_page', 5, type=int) or 5
    if per_page not in (5, 10, 25, 50):
        per_page = 5
    inventory_search = request.args.get('inventory_search', '').strip()[:80]
    inventory_visibility = request.args.get('inventory_visibility', '').strip().lower()
    if inventory_visibility not in {'public', 'private', 'internal', 'unknown'}:
        inventory_visibility = ''
    inventory_archived = request.args.get('inventory_archived', '').strip().lower()
    if inventory_archived not in {'active', 'archived', 'unknown'}:
        inventory_archived = ''
    inventory = read_installation_inventory_for_current_session(
        authorized_installation_id=installation.id,
        page=page,
        per_page=per_page,
        search=inventory_search,
        visibility=inventory_visibility,
        archived=inventory_archived,
    )
    return {
        'inventory': inventory,
        'installation': installation,
        'inventory_search': inventory_search,
        'inventory_visibility': inventory_visibility,
        'inventory_archived': inventory_archived,
    }


def _render_validation_content(installation: SourceInstallation, *, validation_job=None) -> Response:
    canonical = installation.integration_instance
    if canonical is None:
        abort(409)
    return _response(
        'integrations/source_control/github/partials/_detail_validation.html',
        installation=installation,
        canonical=canonical,
        readiness=canonical.readiness_status or 'validation_required',
        action_form=FlaskForm(),
        validation_job=validation_job,
        **_capability_context(canonical),
    )


def _capability_context(canonical) -> dict:
    """Server-backed registry from committed Full Validation, not a live GitHub GET."""
    context = github_capability_context(canonical)
    context['capability_registry'] = build_capability_registry_view(
        context['capability_rows'],
        query=request.args.get('query', ''),
        requirement=request.args.get('requirement', 'all'),
        status=request.args.get('status', 'all'),
        page=request.args.get('page', 1, type=int),
        per_page=request.args.get('per_page', 5, type=int),
        search_fields=('label', 'category', 'description'),
        status_flags=CapabilityStatusFlags(optional_gap=True, unverified=True),
    )
    context['capability_total'] = len(context['capability_rows'])
    return context


def _render_runtime_content(
    installation: SourceInstallation, *, runtime_refresh_job=None, runtime_feedback: str = ''
) -> Response:
    canonical = installation.integration_instance
    if canonical is None:
        abort(409)
    context = _runtime_context(installation)
    if runtime_refresh_job is not None:
        context['runtime_refresh_job'] = runtime_refresh_job
    return _response(
        'integrations/source_control/github/partials/_detail_runtime.html',
        installation=installation,
        canonical=canonical,
        action_form=FlaskForm(),
        runtime_feedback=runtime_feedback,
        **context,
    )


@github_uat_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    require_uat_access()
    records = list_github_uat_installations()
    return _response(
        'integrations/source_control/github/uat_index.html',
        installations=records,
    )


@github_uat_bp.get('/installations/<int:installation_id>')
@permission_required('integrations.manage')
def detail(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    canonical = installation.integration_instance
    if canonical is None:
        abort(409)
    return _response(
        'integrations/source_control/github/uat_detail.html',
        **_inventory_context(installation),
        canonical=canonical,
        **_capability_context(canonical),
        validation_job=_validation_job_for(canonical),
        **_runtime_context(installation),
        action_form=FlaskForm(),
        feedback=request.args.get('feedback', ''),
    )


@github_uat_bp.get('/installations/<int:installation_id>/validation/capabilities')
@permission_required('integrations.manage')
def capability_registry(installation_id: int) -> ResponseReturnValue:
    """Filter committed GitHub permission evidence under existing UAT scope."""
    installation = _installation_or_404(installation_id)
    canonical = installation.integration_instance
    if canonical is None:
        abort(409)
    return _response(
        'integrations/source_control/github/partials/_capability_registry.html',
        installation=installation,
        canonical=canonical,
        **_capability_context(canonical),
    )


def _render_github_edit_connection_result(
    *,
    installation: SourceInstallation,
    canonical: IntegrationInstance,
    form: GitHubAppConnectionEditForm,
    inline_test: bool,
    test_proof: str | None,
    message: str | None,
    rejection: bool,
) -> Response:
    """Preserve the exact HTMX proof and rejected-post response contract."""
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


@github_uat_bp.route('/installations/<int:installation_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def edit_connection(installation_id: int) -> ResponseReturnValue:
    """Guarded edit and tested credential rotation; never rehydrate secrets."""
    installation = _installation_or_404(installation_id)
    canonical = installation.integration_instance
    if canonical is None:
        abort(409)
    form = GitHubAppConnectionEditForm(obj=canonical) if request.method == 'GET' else GitHubAppConnectionEditForm()
    if request.method == 'POST' and canonical.lifecycle_status != 'active':
        abort(409)
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

    return _render_github_edit_connection_result(
        installation=installation,
        canonical=canonical,
        form=form,
        inline_test=inline_test,
        test_proof=test_proof,
        message=message,
        rejection=rejection,
    )


@github_uat_bp.route('/installations/<int:installation_id>/replace', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def replace_installation(installation_id: int) -> ResponseReturnValue:
    """Register an authenticated successor without deleting or rebinding past evidence."""
    predecessor = _installation_or_404(installation_id)
    canonical = predecessor.integration_instance
    if canonical is None:
        abort(409)
    form = GitHubInstallationSuccessorForm()
    if request.method == 'GET':
        form.successor_name.data = f'{canonical.name} Replacement'
        form.app_id.data = predecessor.native_app_id
        form.installation_id.data = predecessor.native_installation_id
        form.account_id.data = predecessor.account.native_account_id if predecessor.account else ''
    action = str(request.form.get('action') or '').strip() if request.method == 'POST' else ''
    inline_test = request.headers.get('HX-Request') == 'true' and action == 'test'
    message = None
    proof = None
    rejected = False

    if request.method == 'POST' and action not in {'test', 'replace'}:
        abort(400)
    if form.validate_on_submit():
        try:
            values = build_successor_connection_input(
                predecessor,
                successor_name=str(form.successor_name.data or ''),
                app_id=str(form.app_id.data or ''),
                installation_id=str(form.installation_id.data or ''),
                account_id=str(form.account_id.data or ''),
                private_key_pem=str(form.private_key_pem.data or ''),
                webhook_secret=str(form.webhook_secret.data or ''),
            )
            if action == 'test':
                test_connection(values)
                proof = issue_github_successor_proof(
                    user_id=int(current_user.id),
                    predecessor_installation_id=predecessor.id,
                    values=values,
                )
                message = 'Replacement installation verified. Registration still requires Save and Full Validation.'
            else:
                valid, message = verify_github_successor_proof(
                    token=str(request.form.get('connection_test_proof') or ''),
                    user_id=int(current_user.id),
                    predecessor_installation_id=predecessor.id,
                    values=values,
                )
                if not valid:
                    rejected = True
                else:
                    # The shared onboarding authority rechecks the same native
                    # identity and grants before creating a separate canonical record.
                    successor = save_tested_connection(values)
                    record_operational_activity(
                        user_id=int(current_user.id),
                        event_type='source_control_installation_replaced',
                        status='success',
                        title='GitHub Replacement Registered',
                        message='A verified successor was registered without deleting the previous installation.',
                        detail='Validate the successor before independently deactivating the predecessor.',
                        action_url=url_for('github_source_uat.detail', installation_id=successor.id),
                        metadata={
                            'predecessor_installation_id': predecessor.id,
                            'successor_installation_id': successor.id,
                            'previous_integration_instance_id': canonical.id,
                            'successor_integration_instance_id': successor.integration_instance_id,
                        },
                        queue_feedback=True,
                    )
                    return redirect(url_for('github_source_uat.detail', installation_id=successor.id))
        except (ValueError, GitHubProviderError, CredentialEncryptionError):
            message = 'Replacement could not be verified or registered. Review identity and App credentials.'
            rejected = True
        except SQLAlchemyError:
            message = 'Replacement could not be saved. Review installation registration.'
            rejected = True
        finally:
            form.clear_sensitive_fields()
    elif request.method == 'POST':
        message = 'Review the replacement fields and try again.'
        rejected = True
        form.clear_sensitive_fields()
    if inline_test:
        response = _response(
            'integrations/source_control/github/partials/_connection_test_result.html',
            verified=bool(proof),
            message=message,
        )
        if proof:
            response.headers['HX-Trigger'] = json.dumps(
                {'github-connection-tested': {'connected': True, 'proof': proof}}
            )
        return response

    response = _response(
        'integrations/source_control/github/replace.html',
        installation=predecessor,
        canonical=canonical,
        form=form,
        message=message,
    )
    if rejected and not form.errors:
        response.status_code = 409
    return response


@github_uat_bp.get('/installations/<int:installation_id>/inventory')
@permission_required('integrations.manage')
def inventory_table(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    context = _inventory_context(installation)
    if request.headers.get('HX-Request') != 'true':
        return redirect(_detail_url(installation_id))
    return _response('integrations/source_control/github/_inventory_table.html', **context)


@github_uat_bp.get('/installations/<int:installation_id>/runtime/jobs')
@permission_required('integrations.manage')
def runtime_jobs(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    if request.headers.get('HX-Request') != 'true':
        return redirect(_detail_url(installation_id, tab='runtime', runtime_view='jobs'))
    return _response(
        'integrations/source_control/github/partials/_runtime_jobs.html',
        installation=installation,
        runtime_table_embedded=True,
        **_runtime_context(installation),
    )


@github_uat_bp.get('/installations/<int:installation_id>/runtime/deliveries')
@permission_required('integrations.manage')
def runtime_deliveries(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    if request.headers.get('HX-Request') != 'true':
        return redirect(_detail_url(installation_id, tab='runtime', runtime_view='deliveries'))
    return _response(
        'integrations/source_control/github/partials/_runtime_deliveries.html',
        installation=installation,
        runtime_table_embedded=True,
        **_runtime_context(installation),
    )


@github_uat_bp.post('/installations/<int:installation_id>/runtime/refresh')
@permission_required('integrations.manage')
def runtime_refresh(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    try:
        job, _created = enqueue_github_app_job(
            installation,
            operation='runtime_refresh',
            requested_by_user_id=int(current_user.id),
        )
    except (GitHubProviderError, RuntimeError, ValueError):
        if request.headers.get('HX-Request') == 'true':
            return _render_runtime_content(installation, runtime_feedback='blocked')
        return redirect(
            url_for('github_source_uat.detail', installation_id=installation_id, feedback='runtime_blocked')
        )
    if request.headers.get('HX-Request') == 'true':
        return _render_runtime_content(installation, runtime_refresh_job=job)
    return redirect(url_for('github_source_uat.detail', installation_id=installation_id, feedback='runtime_queued'))


@github_uat_bp.get('/installations/<int:installation_id>/runtime/refresh/status/<string:task_id>')
@permission_required('integrations.manage')
def runtime_refresh_status(installation_id: int, task_id: str) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    snapshot = build_validation_snapshot(task_id)
    if (
        not validate_snapshot_access(
            snapshot,
            integration_type='source_control',
            integration_instance_id=installation.integration_instance_id,
        )
        or snapshot.get('operation') != 'runtime_refresh'
    ):
        abort(404)
    response = _render_runtime_content(installation, runtime_refresh_job=snapshot)
    return validation_poll_response(response.get_data(as_text=True), snapshot=snapshot)


@github_uat_bp.post('/installations/<int:installation_id>/validate')
@permission_required('integrations.manage')
def validate(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    try:
        validation_job, _created = enqueue_github_app_job(
            installation,
            operation='full_validation',
            requested_by_user_id=int(current_user.id),
        )
    except (GitHubProviderError, RuntimeError, ValueError):
        return redirect(
            url_for('github_source_uat.detail', installation_id=installation_id, feedback='validation_blocked')
        )
    if request.headers.get('HX-Request') == 'true':
        return _render_validation_content(installation, validation_job=validation_job)
    return redirect(url_for('github_source_uat.detail', installation_id=installation_id, feedback='validation_queued'))


@github_uat_bp.get('/installations/<int:installation_id>/validate/status/<string:task_id>')
@permission_required('integrations.manage')
def validation_status(installation_id: int, task_id: str) -> ResponseReturnValue:
    """Poll admitted validation task without accessing live provider state."""
    installation = _installation_or_404(installation_id)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='source_control',
        integration_instance_id=installation.integration_instance_id,
    ):
        abort(404)
    response = _render_validation_content(installation, validation_job=snapshot)
    return validation_poll_response(response.get_data(as_text=True), snapshot=snapshot)


@github_uat_bp.post('/installations/<int:installation_id>/sync')
@permission_required('integrations.manage')
def synchronize(installation_id: int) -> ResponseReturnValue:
    installation = _installation_or_404(installation_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    detail_url = url_for('github_source_uat.detail', installation_id=installation_id, tab='inventory')
    feedback_status = 'info'
    feedback_title = 'Repository Sync Queued'
    feedback_message = (
        'Repository synchronization was requested. Review committed inventory after the worker completes.'
    )
    try:
        enqueue_source_repository_sync(
            requested_by_user_id=int(current_user.id),
            trigger_type='uat',
            installation_record_id=installation_id,
        )
    except (NoEligibleSourceControlTargets, RuntimeError, ValueError):
        feedback_status = 'warning'
        feedback_title = 'Repository Sync Blocked'
        feedback_message = 'Repository synchronization could not start. Review Full Validation and worker readiness.'
    record_operational_activity(
        user_id=int(current_user.id),
        event_type='source_control_repository_sync_' + ('queued' if feedback_status == 'info' else 'blocked'),
        status=feedback_status,
        title=feedback_title,
        message=feedback_message,
        action_url=detail_url,
        metadata={
            'source_installation_id': installation.id,
            'integration_instance_id': installation.integration_instance_id,
            'feedback_delivery': 'toast',
        },
        queue_feedback=True,
    )
    return redirect(detail_url)


@github_uat_bp.post('/installations/<int:installation_id>/delete')
@permission_required('integrations.manage')
def delete_connection(installation_id: int) -> ResponseReturnValue:
    """Retire a KAORI connection without deleting provider or committed evidence."""
    installation = _installation_or_404(installation_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    canonical = installation.integration_instance
    if (
        canonical is None
        or canonical.id != installation.integration_instance_id
        or canonical.integration_type != 'source_control'
        or canonical.provider_key != 'github'
        or canonical.adapter_key != 'github_rest_v3'
    ):
        abort(409)
    if canonical.lifecycle_status != 'active':
        abort(409)
    guard = provider_deletion_guard(integration_type='source_control', integration_instance_id=canonical.id)
    if guard.blocked:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='source_control_connection_deletion_blocked',
            status='warning',
            title='Connection Deletion Blocked',
            message='Active KAORI jobs still reference this GitHub connection. Finish them before deleting it.',
            action_url=url_for('github_source_uat.detail', installation_id=installation.id, tab='inventory'),
            metadata={
                'source_installation_id': installation.id,
                'integration_instance_id': canonical.id,
                'active_jobs': guard.active_jobs,
                'feedback_delivery': 'toast',
            },
            queue_feedback=True,
        )
        return redirect(url_for('github_source_uat.detail', installation_id=installation.id, tab='inventory'))

    former_name = canonical.name
    try:
        retire_github_connection(canonical)
    except SQLAlchemyError:
        abort(409)

    record_operational_activity(
        user_id=int(current_user.id),
        event_type='source_control_connection_retired',
        status='success',
        title='GitHub Connection Deleted',
        message='The connection was removed from active KAORI use. GitHub permissions and committed history were preserved.',
        metadata={
            'source_installation_id': installation.id,
            'integration_instance_id': canonical.id,
            'connection_name': former_name,
            'feedback_delivery': 'toast',
        },
        queue_feedback=True,
    )
    return redirect(url_for('github_source_uat.index'))
