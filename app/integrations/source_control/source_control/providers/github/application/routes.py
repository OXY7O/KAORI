"""GitHub App registration workspace, admission gated and RBAC/CSRF protected.

Read-only UI preview is available while the provider is planned; no secrets
are accepted, no external provider requests run and no database records are
written until full provider admission is approved.
"""

from __future__ import annotations

import json

from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.common.pagination import build_pagination_window, paginate_query, pagination_payload
from app.extensions.db import db
from app.extensions.limiter import limiter
from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.application.forms import (
    GitHubAppConnectionForm,
)
from app.integrations.source_control.source_control.providers.github.application.registration_proof import (
    issue_github_registration_proof,
    verify_github_registration_proof,
)
from app.integrations.source_control.source_control.providers.github.registration import (
    save_tested_connection,
    test_connection,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError
from app.integrations.source_control.source_control.providers.github.webhook_inbox import (
    claim_verified_delivery,
)
from app.integrations.source_control.uat_access import local_super_admin, require_uat_access, uat_enabled
from app.models.integration import IntegrationInstance
from app.models.source_control import (
    SourceInstallation,
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
)
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.security.credentials import CredentialEncryptionError

github_source_bp = Blueprint('github_source', __name__, url_prefix='/integrations/source-control/github')


def _available() -> bool:
    return provider_kind('source_control', 'github').available


def _respond(template: str, **context) -> ResponseReturnValue:
    response = make_response(render_template(template, **context))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


def _notification() -> dict:
    return get_navigation_notification_context(user_id=int(current_user.id))


@github_source_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    """Read the GitHub connection and repository coverage from committed KAORI state."""
    available = _available()
    uat_workspace_enabled = available and uat_enabled() and local_super_admin(current_user)
    active_tab = request.args.get('tab', 'coverage').strip()
    if active_tab not in {'coverage', 'registry'}:
        active_tab = 'coverage'

    selected_query = request.args.get('q', '').strip()[:120]
    selected_environment = request.args.get('environment', '').strip()[:40]
    selected_readiness = request.args.get('readiness', '').strip()[:40]
    requested_page = request.args.get('page', 1, type=int) or 1
    requested_per_page = request.args.get('per_page', 5, type=int) or 5

    selected_coverage_query = request.args.get('coverage_q', '').strip()[:120]
    selected_coverage_environment = request.args.get('coverage_environment', '').strip()[:40]
    selected_coverage_status = request.args.get('coverage_status', '').strip()[:40]
    requested_coverage_page = request.args.get('coverage_page', 1, type=int) or 1
    requested_coverage_per_page = request.args.get('coverage_per_page', 5, type=int) or 5

    if available:
        base = IntegrationInstance.query.filter_by(
            integration_type='source_control',
            provider_key='github',
        )
        total = base.count()
        ready = base.filter_by(enabled=True, lifecycle_status='active', readiness_status='ready').count()

        # Only committed generations with effective-dated grants are coverage
        # evidence. A tested/registered installation alone is not inventory.
        coverage_base = (
            db.session.query(
                SourceRepositoryGrant,
                SourceRepository,
                SourceInstallation,
                IntegrationInstance,
                SourceRepositoryCollectionState,
            )
            .join(SourceRepository, SourceRepository.id == SourceRepositoryGrant.repository_id)
            .join(SourceInstallation, SourceInstallation.id == SourceRepositoryGrant.installation_id)
            .join(IntegrationInstance, IntegrationInstance.id == SourceInstallation.integration_instance_id)
            .join(
                SourceRepositoryCollectionState,
                SourceRepositoryCollectionState.installation_id == SourceInstallation.id,
            )
            .filter(
                SourceRepositoryGrant.valid_until.is_(None),
                SourceRepositoryCollectionState.committed_generation > 0,
                SourceInstallation.provider_key == 'github',
                SourceInstallation.host_key == 'github.com',
                SourceRepository.provider_key == 'github',
                SourceRepository.host_key == 'github.com',
                IntegrationInstance.integration_type == 'source_control',
                IntegrationInstance.provider_key == 'github',
            )
        )
        grants = coverage_base.count()
        committed_collections = (
            SourceRepositoryCollectionState.query.join(
                SourceInstallation,
                SourceInstallation.id == SourceRepositoryCollectionState.installation_id,
            )
            .join(
                IntegrationInstance,
                IntegrationInstance.id == SourceInstallation.integration_instance_id,
            )
            .filter(
                SourceRepositoryCollectionState.committed_generation > 0,
                SourceInstallation.provider_key == 'github',
                SourceInstallation.host_key == 'github.com',
                IntegrationInstance.integration_type == 'source_control',
                IntegrationInstance.provider_key == 'github',
            )
            .count()
        )

        coverage_query = coverage_base
        if selected_coverage_query:
            coverage_term = f'%{selected_coverage_query}%'
            coverage_query = coverage_query.filter(
                or_(
                    SourceRepository.full_name.ilike(coverage_term),
                    SourceRepository.name.ilike(coverage_term),
                    IntegrationInstance.name.ilike(coverage_term),
                    SourceInstallation.native_installation_id.ilike(coverage_term),
                )
            )
        if selected_coverage_environment:
            coverage_query = coverage_query.filter(IntegrationInstance.environment == selected_coverage_environment)
        if selected_coverage_status:
            coverage_query = coverage_query.filter(SourceRepositoryCollectionState.coverage == selected_coverage_status)
        coverage_rows, coverage_pagination = paginate_query(
            coverage_query.order_by(
                SourceRepository.full_name.asc(),
                SourceInstallation.id.asc(),
                SourceRepositoryGrant.id.asc(),
            ),
            page=requested_coverage_page,
            per_page=requested_coverage_per_page,
        )
        coverage_environment_options = [
            item[0] for item in coverage_base.with_entities(IntegrationInstance.environment).distinct().all() if item[0]
        ]
        coverage_status_options = [
            item[0]
            for item in coverage_base.with_entities(SourceRepositoryCollectionState.coverage).distinct().all()
            if item[0]
        ]

        query = base
        if selected_query:
            term = f'%{selected_query}%'
            query = query.filter(
                or_(
                    IntegrationInstance.name.ilike(term),
                    IntegrationInstance.description.ilike(term),
                )
            )
        if selected_environment:
            query = query.filter(IntegrationInstance.environment == selected_environment)
        if selected_readiness:
            query = query.filter(IntegrationInstance.readiness_status == selected_readiness)

        rows, pagination = paginate_query(
            query.order_by(IntegrationInstance.created_at.desc(), IntegrationInstance.id.desc()),
            page=requested_page,
            per_page=requested_per_page,
        )
        installations = (
            SourceInstallation.query.filter(
                SourceInstallation.integration_instance_id.in_([row.id for row in rows]),
                SourceInstallation.provider_key == 'github',
                SourceInstallation.host_key == 'github.com',
            ).all()
            if rows
            else []
        )
        installation_by_instance = {row.integration_instance_id: row for row in installations}
        environment_options = [
            item[0] for item in base.with_entities(IntegrationInstance.environment).distinct().all() if item[0]
        ]
        readiness_options = [
            item[0] for item in base.with_entities(IntegrationInstance.readiness_status).distinct().all() if item[0]
        ]
    else:
        # No provider admission means the inventory is not observed, not ready.
        total = ready = grants = None
        committed_collections = 0
        rows = []
        pagination = pagination_payload(build_pagination_window(total_items=0))
        installation_by_instance = {}
        environment_options = []
        readiness_options = []
        coverage_rows = []
        coverage_pagination = pagination_payload(build_pagination_window(total_items=0))
        coverage_environment_options = []
        coverage_status_options = []

    context = {
        'available': available,
        'registered': total,
        'ready': ready,
        'stats': {
            'total': total if total is not None else 'Not Observed',
            'ready': ready if ready is not None else 'Not Observed',
            'attention': total - ready if total is not None and ready is not None else 'Not Observed',
            'grants': grants if grants is not None else 'Not Observed',
        },
        'active_tab': active_tab,
        'rows': rows,
        'pagination': pagination,
        'installation_by_instance': installation_by_instance,
        'selected_query': selected_query,
        'selected_environment': selected_environment,
        'selected_readiness': selected_readiness,
        'environment_options': sorted(environment_options),
        'readiness_options': sorted(readiness_options),
        'registry_has_active_filters': bool(selected_query or selected_environment or selected_readiness),
        'coverage_rows': coverage_rows,
        'coverage_observed': committed_collections > 0,
        'coverage_pagination': coverage_pagination,
        'selected_coverage_query': selected_coverage_query,
        'selected_coverage_environment': selected_coverage_environment,
        'selected_coverage_status': selected_coverage_status,
        'coverage_environment_options': sorted(coverage_environment_options),
        'coverage_status_options': sorted(coverage_status_options),
        'coverage_has_active_filters': bool(
            selected_coverage_query or selected_coverage_environment or selected_coverage_status
        ),
        'uat_workspace_enabled': uat_workspace_enabled,
        'notification_context': _notification(),
    }
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'github-connection-registry':
            return _respond('integrations/source_control/github/partials/_connection_registry.html', **context)
        if target == 'github-integration-coverage':
            return _respond('integrations/source_control/github/partials/_integration_coverage.html', **context)
    return _respond('integrations/source_control/github/index.html', **context)


@github_source_bp.route('/connections/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def new_connection() -> ResponseReturnValue:
    """A public POST cannot bypass the planned provider gate."""
    available = _available()
    if available:
        # Until #724, provider activation is restricted to the explicit
        # Dev Container UAT boundary; integr.manage alone is insufficient.
        require_uat_access()
    if request.method == 'POST' and not available:
        abort(409)
    form = GitHubAppConnectionForm()
    action = str(request.form.get('action') or '').strip() if request.method == 'POST' else ''
    inline_test = request.headers.get('HX-Request') == 'true' and action == 'test'
    message: str | None = None
    verified_scope: str | None = None
    registration_rejected = False
    test_proof: str | None = None

    if available and form.validate_on_submit():
        if action not in {'test', 'save'}:
            abort(400)
        values = form.to_input()
        try:
            if action == 'test':
                observation = test_connection(values)
                verified_scope = observation.repository_selection
                test_proof = issue_github_registration_proof(user_id=int(current_user.id), values=values)
                message = (
                    'GitHub App installation verified. This is not Full Validation; '
                    'no repository inventory has been committed.'
                )
            else:
                valid, reason = verify_github_registration_proof(
                    token=str(request.form.get('connection_test_proof') or '').strip(),
                    user_id=int(current_user.id),
                    values=values,
                )
                if not valid:
                    message = reason
                    registration_rejected = True
                else:
                    # A valid proof is a precondition, not a substitute for
                    # the live GitHub installation identity recheck on save.
                    save_tested_connection(values)
                    record_operational_activity(
                        user_id=int(current_user.id),
                        event_type='source_control_connection_registered',
                        status='success',
                        title='GitHub App Connection Registered',
                        message='Installation identity was verified and registered.',
                        detail='Run Full Validation before consuming Source Control evidence.',
                        action_url=url_for('github_source.index'),
                        queue_feedback=True,
                    )
                    return redirect(url_for('github_source.index', tab='registry'))
        except (GitHubProviderError, ValueError, CredentialEncryptionError):
            message = (
                'GitHub App connection could not be verified. Review App identity, installation scope and credentials.'
            )
        except SQLAlchemyError:
            message = 'GitHub App connection could not be saved. Review integration configuration.'
        finally:
            # Flask-WTF otherwise mirrors sensitive fields into an HTML response.
            form.clear_sensitive_fields()
    elif request.method == 'POST':
        message = 'Review the highlighted configuration fields and try again.'
        form.clear_sensitive_fields()

    if inline_test:
        response = make_response(
            render_template(
                'integrations/source_control/github/partials/_connection_test_result.html',
                verified=bool(test_proof),
                message=message,
            )
        )
        if test_proof:
            # HTMX publishes this event to the Alpine form; no credentials or
            # access tokens are reflected in the fragment or event payload.
            response.headers['HX-Trigger'] = json.dumps(
                {'github-connection-tested': {'connected': True, 'proof': test_proof}}
            )
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response

    response = _respond(
        'integrations/source_control/github/form.html',
        form=form,
        available=available,
        message=message,
        verified_scope=verified_scope,
        notification_context=_notification(),
    )
    if registration_rejected:
        response.status_code = 409
    return response


@github_source_bp.post('/webhook')
@limiter.limit('30 per minute')
def receive_signed_webhook() -> ResponseReturnValue:
    """Disabled-by-default signed GitHub App transport, never source evidence.

    This externally callable route is deliberately unavailable while either
    independent admission gate is closed. It stores only authenticated,
    deduplicated envelope metadata; it NEVER enqueues a job on request.
    """
    if not current_app.config.get('SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED', False) or not _available():
        abort(404)

    # Reject oversized and lengthless deliveries before parsing/decryption.
    if request.content_length is None:
        abort(411)
    if request.content_length > 262_144:
        abort(413)
    request.max_content_length = 262_144
    payload = request.get_data(cache=False)
    if not payload or len(payload) > 262_144:
        abort(413)
    if request.mimetype != 'application/json':
        abort(415)

    # The installation ID is an untrusted lookup hint only. Its App-specific
    # shared HMAC secret independently proves provider authenticity later.
    try:
        envelope = json.loads(payload)
        native_installation = envelope.get('installation')
        native_id = native_installation.get('id') if isinstance(native_installation, dict) else None
    except (ValueError, UnicodeDecodeError, AttributeError):
        abort(400)
    if not isinstance(native_id, int) or isinstance(native_id, bool) or native_id <= 0:
        abort(400)

    candidates = (
        SourceInstallation.query.filter_by(
            host_key='github.com',
            provider_key='github',
            native_installation_id=str(native_id),
        )
        .limit(2)
        .all()
    )
    if len(candidates) != 1:
        abort(401)
    try:
        claim_verified_delivery(
            installation=candidates[0],
            payload=payload,
            headers=request.headers,
            session=db.session,
        )
        db.session.commit()
    except GitHubWebhookError:
        db.session.rollback()
        abort(401)
    except Exception:
        db.session.rollback()
        # The response cannot include DB diagnostics, signatures or PEM.
        abort(503)

    response = make_response('', 202)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response
