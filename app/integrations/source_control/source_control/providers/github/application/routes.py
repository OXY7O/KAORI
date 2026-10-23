"""GitHub App registration workspace, admission gated and RBAC/CSRF protected.

Read-only UI preview is available while the provider is planned; no secrets
are accepted, no external provider requests run and no database records are
written until full provider admission is approved.
"""

from __future__ import annotations

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.application.forms import (
    GitHubAppConnectionForm,
)
from app.integrations.source_control.source_control.providers.github.registration import (
    save_tested_connection,
    test_connection,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
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
            message = 'GitHub App connection could not be verified. Review App identity, installation scope and credentials.'
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
