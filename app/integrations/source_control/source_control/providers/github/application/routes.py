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
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.extensions.limiter import limiter
from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.application.forms import (
    GitHubAppConnectionForm,
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
from app.integrations.source_control.uat_access import local_super_admin, uat_enabled
from app.models.source_control import SourceInstallation
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.security.credentials import CredentialEncryptionError

github_source_bp = Blueprint(
    'github_source', __name__, url_prefix='/integrations/source-control/github'
)


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
    """Provider onboarding landing, not a fabricated repository inventory."""
    available = _available()
    registered: int | None = None
    ready: int | None = None
    if available:
        from app.models.integration import IntegrationInstance

        query = IntegrationInstance.query.filter_by(
            integration_type='source_control', provider_key='github'
        )
        registered = query.count()
        ready = query.filter_by(
            enabled=True, lifecycle_status='active', readiness_status='ready'
        ).count()
    return _respond(
        'integrations/source_control/github/index.html',
        available=available, registered=registered, ready=ready,
        uat_workspace_enabled=uat_enabled() and local_super_admin(current_user),
        notification_context=_notification(),
    )


@github_source_bp.route('/connections/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def new_connection() -> ResponseReturnValue:
    """A public POST cannot bypass the planned provider gate."""
    available = _available()
    if request.method == 'POST' and not available:
        abort(409)
    form = GitHubAppConnectionForm()
    message: str | None = None
    verified_scope: str | None = None
    if available and form.validate_on_submit():
        values = form.to_input()
        action = str(request.form.get('action') or '').strip()
        if action not in {'test', 'save'}:
            abort(400)
        try:
            if action == 'test':
                observation = test_connection(values)
                verified_scope = observation.repository_selection
                message = (
                    'GitHub App installation verified. This is not Full Validation; '
                    'no repository inventory has been committed.'
                )
            else:
                instance = save_tested_connection(values)
                record_operational_activity(
                    user_id=int(current_user.id), event_type='source_control_connection_registered',
                    status='success', title='GitHub App Connection Registered',
                    message='Installation identity was verified and registered.',
                    detail='Run Full Validation before consuming Source Control evidence.',
                    action_url=url_for('github_source.index'), queue_feedback=True,
                )
                return redirect(url_for('github_source.index'))
        except (GitHubProviderError, ValueError, CredentialEncryptionError):
            message = (
                'GitHub App connection could not be verified. '
                'Review App identity, installation scope and credentials.'
            )
        except SQLAlchemyError:
            message = 'GitHub App connection could not be saved. Review integration configuration.'
        finally:
            # Flask-WTF otherwise mirrors input back to templates after POST.
            form.clear_sensitive_fields()
    elif request.method == 'POST':
        message = 'Review the highlighted configuration fields and try again.'
        form.clear_sensitive_fields()
    return _respond(
        'integrations/source_control/github/form.html',
        form=form, available=available, message=message,
        verified_scope=verified_scope, notification_context=_notification(),
    )


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

    candidates = SourceInstallation.query.filter_by(
        host_key='github.com', provider_key='github',
        native_installation_id=str(native_id),
    ).limit(2).all()
    if len(candidates) != 1:
        abort(401)
    try:
        claim_verified_delivery(
            installation=candidates[0],
            payload=payload, headers=request.headers,
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
