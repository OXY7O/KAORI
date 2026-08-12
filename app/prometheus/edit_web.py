from __future__ import annotations

import logging

from flask import abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.common.http import is_htmx_request
from app.integrations.prometheus.exceptions import PrometheusError
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.prometheus.forms import PrometheusInstanceForm
from app.prometheus.presentation import build_instance_context
from app.prometheus.repository import get_instance
from app.prometheus.service import save_prometheus_instance

logger = logging.getLogger(__name__)


def edit_instance_response(instance_id: int) -> ResponseReturnValue:
    instance = get_instance(instance_id)
    if instance is None:
        abort(404)
    form = PrometheusInstanceForm(obj=instance)
    setattr(form, '_existing_instance', instance)
    feedback = None
    is_htmx = is_htmx_request()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                instance = save_prometheus_instance(form, instance=instance)
            except (PrometheusError, SQLAlchemyError, ValueError) as exc:
                logger.exception('Prometheus instance update failed for %s.', instance_id)
                feedback = record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_update_failed',
                    status='error',
                    title='Prometheus connection not updated',
                    message=f'KAORI could not update {instance.name}.',
                    detail=str(exc) or 'Review the submitted connection settings before retrying.',
                    action_url=url_for('prometheus.edit_instance', instance_id=instance.id),
                    action_label='Review Prometheus configuration',
                    action_icon='settings-2',
                    metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
                    queue_feedback=not is_htmx,
                )
            else:
                registry_url = url_for('integrations.prometheus')
                feedback = record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_updated',
                    status='success',
                    title='Prometheus Connection Updated',
                    message=f'{instance.name} connection settings were saved.',
                    detail='Readiness returned to Validation Required until Full Validation rebuilds provider evidence.',
                    action_url=registry_url,
                    action_label='Back to Prometheus Registry',
                    action_icon='chart-spline',
                    metadata={'instance_id': instance.id},
                    queue_feedback=True,
                )
                if is_htmx:
                    response = make_response('', 204)
                    response.headers['HX-Redirect'] = registry_url
                    return response
                return redirect(registry_url)
        else:
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_update_rejected',
                status='error',
                title='Prometheus connection not updated',
                message=f'KAORI could not update {instance.name}.',
                detail='Review the highlighted configuration fields before saving again.',
                action_url=url_for('prometheus.edit_instance', instance_id=instance.id),
                action_label='Review Prometheus configuration',
                action_icon='settings-2',
                metadata={'instance_id': instance.id, 'fields': sorted(form.errors)},
                queue_feedback=not is_htmx,
            )

    context = build_instance_context(instance)
    context.update(
        form=form,
        instance=instance,
        initial_cluster=None,
        registration_proof=None,
        operation_feedback=feedback,
        notification_context=(
            get_navigation_notification_context(user_id=int(current_user.id)) if feedback is not None else None
        ),
    )
    return render_template('prometheus/instance_form.html', **context)
