"""Local OpenBao registry and connection controls."""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.rbac.decorators import permission_required
from app.integrations.secrets_management.secrets_pki.providers.openbao.forms import OpenBaoConnectionForm
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import (
    get_connection,
    list_connections,
    local_provider_enabled,
    register_connection,
    runtime_history,
)
from app.integrations.validation.state import get_active_validation_task_id
from app.integrations.validation.web import enqueue_instance_validation, enqueue_runtime_health_refresh
from app.platform_operations.notifications.service import create_transient_feedback
from app.security.credentials import CredentialEncryptionError

openbao_bp = Blueprint('openbao', __name__, url_prefix='/integrations/secrets-management/secrets-pki/openbao')


def _require_local() -> None:
    if not local_provider_enabled():
        abort(404)


@openbao_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    _require_local()
    rows, pagination = list_connections(
        page=request.args.get('page', 1, type=int), per_page=request.args.get('per_page', 5, type=int)
    )
    return render_template('integrations/secrets_management/openbao/index.html', rows=rows, pagination=pagination)


@openbao_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def new_instance() -> ResponseReturnValue:
    _require_local()
    form = OpenBaoConnectionForm()
    if form.validate_on_submit():
        try:
            row = register_connection(form.to_input(), actor_id=int(current_user.id))
        except (ValueError, SQLAlchemyError, CredentialEncryptionError):
            create_transient_feedback(
                status='error',
                title='OpenBao registration failed',
                message='Review approved HTTPS, cluster UUID, scoped AppRole, unique identity and encryption.',
                queue_feedback=True,
            )
        else:
            create_transient_feedback(
                status='success',
                title='OpenBao connection registered',
                message='Connection evidence committed. Credential authority remains pending.',
                queue_feedback=True,
            )
            return redirect(url_for('openbao.detail', instance_id=row.id), code=303)
    form.secret_id.data = ''
    return render_template('integrations/secrets_management/openbao/form.html', form=form)


@openbao_bp.get('/instances/<int:instance_id>')
@permission_required('integrations.manage')
def detail(instance_id: int) -> ResponseReturnValue:
    _require_local()
    row = get_connection(instance_id)
    if row is None:
        abort(404)
    active = {
        operation: get_active_validation_task_id(
            integration_type='secrets_pki', operation=operation, integration_instance_id=row.integration_instance_id
        )
        for operation in ('full_validation', 'runtime_refresh')
    }
    return render_template(
        'integrations/secrets_management/openbao/detail.html', row=row, active=active, history=runtime_history(row)
    )


@openbao_bp.post('/instances/<int:instance_id>/<string:operation>')
@permission_required('integrations.manage')
def validate_connection(instance_id: int, operation: str) -> ResponseReturnValue:
    _require_local()
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)
    if set(request.form) != {'csrf_token'} or len(request.form.getlist('csrf_token')) != 1:
        abort(400)
    row = get_connection(instance_id)
    if row is None or not row.enabled or row.integration_instance.lifecycle_status != 'active':
        abort(404)
    if operation not in ('validate', 'refresh'):
        abort(404)
    enqueue = enqueue_instance_validation if operation == 'validate' else enqueue_runtime_health_refresh
    try:
        enqueue(
            integration_type='secrets_pki',
            integration_instance_id=row.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
    except (RuntimeError, ValueError, SQLAlchemyError, OSError):
        create_transient_feedback(
            status='error', title='OpenBao validation unavailable',
            message='Review local worker and job admission readiness.', queue_feedback=True,
        )
    else:
        create_transient_feedback(
            status='info', title='OpenBao observation requested',
            message='Check the committed result after the worker completes.', queue_feedback=True,
        )
    return redirect(url_for('openbao.detail', instance_id=instance_id), code=303)
