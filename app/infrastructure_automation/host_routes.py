"""Governed, source-only host registration boundary (#5168)."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.infrastructure_automation.host_enrollment import (
    enroll_host_for_connection,
    host_revision,
    retire_host_for_connection,
    update_host_for_connection,
)
from app.infrastructure_automation.host_forms import (
    AutomationHostEditForm,
    AutomationHostEnrollmentForm,
    AutomationHostRetirementForm,
)
from app.infrastructure_automation.host_registry import (
    AutomationHostIntent,
    AutomationInventoryDenied,
    require_ansible_connection,
)
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.platform_operations.notifications.service import record_operational_activity

bp = Blueprint('infrastructure_automation_hosts', __name__)


@bp.route('/<int:connection_id>/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
@permission_required('inventory.view')
def new(connection_id: int) -> ResponseReturnValue:
    """Enroll a scoped non-production Linux host without admitting execution."""
    connection = db.session.get(IntegrationInstance, connection_id)
    if (
        connection is None
        or connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or not isinstance(connection.environment, str)
    ):
        abort(404)
    environment = connection.environment
    try:
        require_ansible_connection(connection, environment=environment)
    except AutomationInventoryDenied:
        abort(404)

    form = AutomationHostEnrollmentForm()
    error = None
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                host = enroll_host_for_connection(
                    connection,
                    AutomationHostIntent(
                        name=str(form.name.data or '').strip(),
                        environment=environment,
                        address=str(form.address.data or '').strip(),
                        ssh_port=form.ssh_port.data if isinstance(form.ssh_port.data, int) else 0,
                    ),
                    role=str(form.role.data or ''),
                )
            except AutomationInventoryDenied as exc:
                error = str(exc)
            except SQLAlchemyError:
                current_app.logger.exception('Host enrollment failed for connection %s.', connection_id)
                error = 'Unable to save the host. Review the scoped inventory and retry.'
            else:
                record_operational_activity(
                    user_id=int(current_user.id),
                    event_type='automation_host_registered',
                    status='success',
                    title='Host identity registered',
                    message='A Linux host and its inventory role were committed. SSH trust remains required.',
                    action_url=url_for(
                        'platform_operations.infrastructure_automation.index',
                        connection_id=connection.id,
                    ),
                    metadata={
                        'connection_id': connection.id,
                        'host_id': host.id,
                        'feedback_delivery': 'toast',
                    },
                )
                return redirect(
                    url_for('platform_operations.infrastructure_automation.index', connection_id=connection.id)
                )
        else:
            error = 'Review the required host fields and submit the form again.'

    return render_template(
        'infrastructure_automation/host_enrollment.html', connection=connection, form=form, error=error
    )


def _scoped_assignment(connection_id: int, host_id: str, *, lock: bool = False):
    """Never resolve a host except through its selected Ansible connection."""
    query = AutomationInventoryAssignment.query.filter_by(
        integration_instance_id=connection_id, host_id=host_id, enabled=True
    )
    if lock:
        query = query.with_for_update()
    assignment = query.first()
    if assignment is None:
        abort(404)
    return assignment


@bp.route('/<int:connection_id>/<uuid:host_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
@permission_required('inventory.view')
def edit(connection_id: int, host_id) -> ResponseReturnValue:
    """Edit exact committed identity with CSRF and a stale-form guard."""
    connection = db.session.get(IntegrationInstance, connection_id)
    if connection is None:
        abort(404)
    try:
        require_ansible_connection(connection, environment=connection.environment)
    except AutomationInventoryDenied:
        abort(404)
    assignment = _scoped_assignment(connection_id, str(host_id), lock=request.method == 'POST')
    if request.method == 'POST':
        db.session.refresh(assignment.host, with_for_update=True)
    host = assignment.host
    revision = host_revision(assignment)
    form = (
        AutomationHostEditForm()
        if request.method == 'POST'
        else AutomationHostEditForm(
            data={
                'name': host.name,
                'address': host.address,
                'ssh_port': host.ssh_port,
                'role': assignment.role,
                'expected_revision': revision,
            }
        )
    )
    error = None
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                update_host_for_connection(
                    connection,
                    assignment,
                    AutomationHostIntent(
                        name=str(form.name.data or '').strip(),
                        environment=connection.environment,
                        address=str(form.address.data or '').strip(),
                        ssh_port=form.ssh_port.data if isinstance(form.ssh_port.data, int) else 0,
                    ),
                    role=str(form.role.data or ''),
                    expected_revision=str(form.expected_revision.data or ''),
                )
            except AutomationInventoryDenied as exc:
                error = str(exc)
            except SQLAlchemyError:
                current_app.logger.exception('Host edit failed for connection %s.', connection_id)
                error = 'Unable to update the scoped host inventory.'
            else:
                record_operational_activity(
                    user_id=int(current_user.id),
                    event_type='automation_host_updated',
                    status='success',
                    title='Host identity updated',
                    message='The committed host inventory changed; review any previous Plan again.',
                    action_url=url_for(
                        'platform_operations.infrastructure_automation.index', connection_id=connection_id
                    ),
                    metadata={'connection_id': connection_id, 'host_id': host.id, 'feedback_delivery': 'toast'},
                )
                return redirect(
                    url_for('platform_operations.infrastructure_automation.index', connection_id=connection_id)
                )
        else:
            error = 'Review the required fields and submit the form again.'
    return render_template(
        'infrastructure_automation/host_edit.html',
        connection=connection,
        host=host,
        form=form,
        retirement_form=AutomationHostRetirementForm(data={'expected_revision': revision}),
        error=error,
    )


@bp.post('/<int:connection_id>/<uuid:host_id>/retire')
@permission_required('integrations.manage')
@permission_required('inventory.view')
def retire(connection_id: int, host_id) -> ResponseReturnValue:
    """Only an explicitly confirmed, CSRF-protected POST retires an exclusive asset."""
    connection = db.session.get(IntegrationInstance, connection_id)
    if connection is None:
        abort(404)
    try:
        require_ansible_connection(connection, environment=connection.environment)
    except AutomationInventoryDenied:
        abort(404)
    assignment = _scoped_assignment(connection_id, str(host_id), lock=True)
    db.session.refresh(assignment.host, with_for_update=True)
    form = AutomationHostRetirementForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        host = retire_host_for_connection(
            connection,
            assignment,
            expected_revision=str(form.expected_revision.data or ''),
            confirmation=str(form.confirm_name.data or '').strip(),
        )
    except AutomationInventoryDenied as exc:
        current_app.logger.info('Host retirement denied for connection %s: %s', connection_id, type(exc).__name__)
        abort(409, description=str(exc))
    except SQLAlchemyError:
        current_app.logger.exception('Host retirement failed for connection %s.', connection_id)
        abort(503)
    record_operational_activity(
        user_id=int(current_user.id),
        event_type='automation_host_retired',
        status='success',
        title='Host inventory identity retired',
        message='The host membership is disabled. Review previous Plans; fingerprint-bound invalidation is gated under #5163.',
        action_url=url_for('platform_operations.infrastructure_automation.index', connection_id=connection_id),
        metadata={'connection_id': connection_id, 'host_id': host.id, 'feedback_delivery': 'toast'},
    )
    return redirect(url_for('platform_operations.infrastructure_automation.index', connection_id=connection_id))
