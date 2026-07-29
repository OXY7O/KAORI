import logging

from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.web import render_reports_unavailable
from app.reports.report_templates.service import (
    create_custom_template,
    delete_custom_template,
    duplicate_custom_template,
    duplicate_system_template,
    get_report_templates_payload,
    update_custom_template,
)


logger = logging.getLogger(__name__)


def _current_user_id() -> int:
    return int(getattr(current_user, 'id', 0) or 0)


def _queue_template_validation(errors: list[str]) -> None:
    queue_transient_feedback(
        status='error',
        title='Report template validation failed',
        message='Review the report template fields and try again.',
        detail=' '.join(errors),
    )


def _record_template_feedback(
    *,
    event_type: str,
    success: bool,
    title: str,
    message: str,
    template_id: int | str | None = None,
) -> None:
    action_url = url_for('reports.report_templates')
    if isinstance(template_id, int):
        action_url = url_for('reports.report_templates', edit_template_id=template_id)
    metadata: dict[str, object] = {'outcome': 'success' if success else 'failed'}
    if template_id is not None:
        metadata['template_id'] = template_id
    record_operational_activity(
        user_id=_current_user_id(),
        event_type=event_type,
        status='success' if success else 'error',
        title=title,
        message=message,
        action_url=action_url,
        action_label='View report templates',
        metadata=metadata,
        queue_feedback=True,
    )


@permission_required('reports.manage_templates')
def report_templates() -> ResponseReturnValue:
    try:
        payload = get_report_templates_payload(request.args)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Report Templates could not be loaded.')
        return render_reports_unavailable(
            page_title='Report Templates',
            description='Manage reusable report structures and section contracts.',
            reason='KAORI could not load the template catalog. Existing templates remain unchanged while dependencies are reviewed.',
            retry_url=url_for('reports.report_templates'),
        )
    return render_template('reports/report_templates/index.html', payload=payload)


@permission_required('reports.manage_templates')
def create_report_template() -> ResponseReturnValue:
    success, errors, template = create_custom_template(request.form, _current_user_id())
    if success and template is not None:
        _record_template_feedback(
            event_type='report_template_create',
            success=True,
            title='Report template created',
            message='Custom report template created successfully.',
            template_id=template.id,
        )
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))

    _queue_template_validation(errors)
    return redirect(url_for('reports.report_templates'))


@permission_required('reports.manage_templates')
def update_report_template(template_id: int) -> ResponseReturnValue:
    success, errors, template = update_custom_template(template_id, request.form)
    if success and template is not None:
        _record_template_feedback(
            event_type='report_template_update',
            success=True,
            title='Report template updated',
            message='Custom report template updated successfully.',
            template_id=template.id,
        )
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))

    _queue_template_validation(errors)
    return redirect(url_for('reports.report_templates', edit_template_id=template_id))


@permission_required('reports.manage_templates')
def delete_report_template(template_id: int) -> ResponseReturnValue:
    success, message = delete_custom_template(template_id)
    _record_template_feedback(
        event_type='report_template_delete',
        success=success,
        title='Report template deleted' if success else 'Report template deletion failed',
        message=message,
        template_id=template_id,
    )
    return redirect(url_for('reports.report_templates'))


@permission_required('reports.manage_templates')
def duplicate_system_report_template(template_id: str) -> ResponseReturnValue:
    success, message, template = duplicate_system_template(template_id, _current_user_id())
    result_id = template.id if template is not None else template_id
    _record_template_feedback(
        event_type='report_template_duplicate',
        success=success,
        title='Report template duplicated' if success else 'Report template duplication failed',
        message=message,
        template_id=result_id,
    )
    if template is not None:
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))
    return redirect(url_for('reports.report_templates'))


@permission_required('reports.manage_templates')
def duplicate_custom_report_template(template_id: int) -> ResponseReturnValue:
    success, message, template = duplicate_custom_template(template_id, _current_user_id())
    result_id = template.id if template is not None else template_id
    _record_template_feedback(
        event_type='report_template_duplicate',
        success=success,
        title='Report template duplicated' if success else 'Report template duplication failed',
        message=message,
        template_id=result_id,
    )
    if template is not None:
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))
    return redirect(url_for('reports.report_templates'))
