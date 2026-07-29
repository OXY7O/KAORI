import logging

from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.web import render_reports_unavailable
from app.reports.schedules.service import (
    create_report_schedule,
    delete_report_schedule,
    get_form_state_from_schedule_form,
    get_report_schedules_payload,
    run_schedule_now,
    toggle_report_schedule,
    update_report_schedule,
)


logger = logging.getLogger(__name__)


def _current_user_id() -> int:
    return int(getattr(current_user, 'id', 0) or 0)


def _queue_schedule_validation(errors: list[str]) -> None:
    queue_transient_feedback(
        status='error',
        title='Report schedule validation failed',
        message='Review the report schedule fields and try again.',
        detail=' '.join(errors),
    )


def _record_schedule_feedback(
    *,
    event_type: str,
    success: bool,
    title: str,
    message: str,
    schedule_id: int | None = None,
    report_id: int | None = None,
) -> None:
    action_url = url_for('reports.schedules')
    action_label = 'View report schedules'
    if report_id is not None:
        action_url = url_for('reports.generated_report_detail', report_id=report_id)
        action_label = 'View generated report'
    metadata: dict[str, object] = {'outcome': 'success' if success else 'failed'}
    if schedule_id is not None:
        metadata['schedule_id'] = schedule_id
    if report_id is not None:
        metadata['report_id'] = report_id
    record_operational_activity(
        user_id=_current_user_id(),
        event_type=event_type,
        status='success' if success else 'error',
        title=title,
        message=message,
        action_url=action_url,
        action_label=action_label,
        metadata=metadata,
        queue_feedback=True,
    )


@permission_required('reports.manage_schedules')
def schedules() -> ResponseReturnValue:
    try:
        payload = get_report_schedules_payload(request.args)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Report Schedules could not be loaded.')
        return render_reports_unavailable(
            page_title='Report Schedules',
            description='Automate report generation and delivery through the Reports worker.',
            reason='KAORI could not load schedule definitions or worker readiness. Existing schedules remain stored in the database.',
            retry_url=url_for('reports.schedules'),
        )
    return render_template('reports/schedules/index.html', payload=payload)


@permission_required('reports.manage_schedules')
def create_schedule() -> ResponseReturnValue:
    success, errors, schedule = create_report_schedule(request.form, _current_user_id())
    if success:
        _record_schedule_feedback(
            event_type='report_schedule_create',
            success=True,
            title='Report schedule created',
            message='Report schedule created successfully.',
            schedule_id=getattr(schedule, 'id', None),
        )
        return redirect(url_for('reports.schedules'))

    form_state = get_form_state_from_schedule_form(request.form)
    payload = get_report_schedules_payload(request.args, form_state=form_state, errors=errors)
    _queue_schedule_validation(errors)
    return render_template('reports/schedules/index.html', payload=payload)


@permission_required('reports.manage_schedules')
def update_schedule(schedule_id: int) -> ResponseReturnValue:
    success, errors = update_report_schedule(schedule_id, request.form)
    if success:
        _record_schedule_feedback(
            event_type='report_schedule_update',
            success=True,
            title='Report schedule updated',
            message='Report schedule updated successfully.',
            schedule_id=schedule_id,
        )
    else:
        _queue_schedule_validation(errors)
    return redirect(url_for('reports.schedules'))


@permission_required('reports.manage_schedules')
def toggle_schedule(schedule_id: int) -> ResponseReturnValue:
    success, message = toggle_report_schedule(schedule_id)
    _record_schedule_feedback(
        event_type='report_schedule_toggle',
        success=success,
        title='Report schedule status updated' if success else 'Report schedule status update failed',
        message=message,
        schedule_id=schedule_id,
    )
    return redirect(url_for('reports.schedules'))


@permission_required('reports.manage_schedules')
def delete_schedule(schedule_id: int) -> ResponseReturnValue:
    success, message = delete_report_schedule(schedule_id)
    _record_schedule_feedback(
        event_type='report_schedule_delete',
        success=success,
        title='Report schedule deleted' if success else 'Report schedule deletion failed',
        message=message,
        schedule_id=schedule_id,
    )
    return redirect(url_for('reports.schedules'))


@permission_required('reports.manage_schedules')
def run_schedule(schedule_id: int) -> ResponseReturnValue:
    success, message, report_id = run_schedule_now(schedule_id, requested_by_user_id=_current_user_id())
    _record_schedule_feedback(
        event_type='report_schedule_run',
        success=success,
        title='Report schedule queued' if success else 'Report schedule execution failed',
        message=message,
        schedule_id=schedule_id,
        report_id=report_id,
    )
    if success and report_id is not None:
        return redirect(url_for('reports.generated_report_detail', report_id=report_id))
    return redirect(url_for('reports.schedules'))
