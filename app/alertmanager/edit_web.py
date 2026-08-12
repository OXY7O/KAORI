from __future__ import annotations

import logging

from flask import abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.alertmanager.forms import parse_alertmanager_instance_form
from app.alertmanager.notifications import record_instance_activity
from app.alertmanager.presentation import build_instance_context
from app.alertmanager.service import get_alertmanager_instance, save_alertmanager_instance
from app.common.http import is_htmx_request
from app.notifications.service import get_navigation_notification_context

logger = logging.getLogger(__name__)


def edit_instance_response(instance_id: int) -> ResponseReturnValue:
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    feedback = None
    is_htmx = is_htmx_request()
    draft_form = None

    if request.method == 'POST':
        draft_form = parse_alertmanager_instance_form(request.form)
        try:
            instance = save_alertmanager_instance(form=draft_form, instance=instance)
        except (SQLAlchemyError, ValueError) as exc:
            logger.exception('Alertmanager instance update failed for %s.', instance_id)
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_update_failed',
                status='error',
                title='Alertmanager connection not updated',
                message=f'KAORI could not update {instance.name}.',
                detail=str(exc) or 'Review the submitted connection settings before retrying.',
                metadata={'reason': type(exc).__name__},
                queue_feedback=not is_htmx,
            )
        else:
            registry_url = url_for('integrations.alertmanager')
            feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=instance,
                event_type='alertmanager_instance_updated',
                status='success',
                title='Alertmanager connection updated',
                message=f'{instance.name} connection settings were saved.',
                detail='Readiness is now Validation Required until Full Validation completes.',
                action_url=registry_url,
                action_label='Back to Alertmanager Registry',
                action_icon='siren',
                queue_feedback=not is_htmx,
            )
            if is_htmx:
                response = make_response('', 204)
                response.headers['HX-Redirect'] = registry_url
                return response
            return redirect(registry_url)

    context = build_instance_context(instance)
    context.update(
        instance=instance,
        initial_cluster=None,
        draft_form=draft_form,
        registration_proof=None,
        operation_feedback=feedback,
        notification_context=(
            get_navigation_notification_context(user_id=int(current_user.id)) if feedback is not None else None
        ),
    )
    return render_template('alertmanager/instance_form.html', **context)
