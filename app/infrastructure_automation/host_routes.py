"""Governed, source-only host registration boundary (#5168)."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.infrastructure_automation.host_enrollment import enroll_host_for_connection
from app.infrastructure_automation.host_forms import AutomationHostEnrollmentForm
from app.infrastructure_automation.host_registry import (
    AutomationHostIntent,
    AutomationInventoryDenied,
    require_ansible_connection,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.service import get_connection
from app.platform_operations.notifications.service import record_operational_activity

bp = Blueprint('infrastructure_automation_hosts', __name__)


@bp.route('/<int:connection_id>/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
@permission_required('inventory.view')
def new(connection_id: int) -> ResponseReturnValue:
    """Enroll a scoped non-production Linux host without admitting execution."""
    connection = get_connection(connection_id)
    if connection is None:
        abort(404)
    try:
        require_ansible_connection(connection, environment=connection.environment)
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
                        environment=connection.environment,
                        address=str(form.address.data or '').strip(),
                        ssh_port=int(form.ssh_port.data),
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

    return render_template('infrastructure_automation/host_enrollment.html', connection=connection, form=form, error=error)
