import logging

from flask import (
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.notifications.feedback import OperationalDeliveryPolicy
from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.schedules.job_adapter import run_schedule_now
from app.reports.schedules.service import (
    create_report_schedule,
    delete_report_schedule,
    get_form_state_from_schedule_form,
    get_report_schedules_payload,
    toggle_report_schedule,
    update_report_schedule,
)
from app.reports.web import render_reports_unavailable

logger = logging.getLogger(__name__)


def _current_user_id() -> int:
    return int(getattr(current_user, 'id', 0) or 0)


def _queue_schedule_validation(errors: list[str]) -> None:
    queue_transient_feedback(
        status='error',
        title='Report Schedule Validation Failed',
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
    action_label = 'View Report Schedules'
    if report_id is not None:
        action_url = url_for('reports.generated_reports', focus=report_id, period='all')
        action_label = 'Open Generated Reports'
    metadata: dict[str, object] = {
        'outcome': 'success' if success else 'failed',
        'feedback_delivery': 'toast',
    }
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
        delivery_policy=(
            OperationalDeliveryPolicy.AUDIT_ONLY if success else OperationalDeliveryPolicy.DECK_ON_FAILURE
        ),
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
            title='Report Schedule Created',
            message='The report schedule was created successfully.',
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
            title='Report Schedule Updated',
            message='The report schedule was updated successfully.',
            schedule_id=schedule_id,
        )
        return redirect(url_for('reports.schedules'))

    form_state = get_form_state_from_schedule_form(request.form)
    payload = get_report_schedules_payload(
        request.args,
        errors=errors,
        edit_schedule_id=schedule_id,
        edit_form_state=form_state,
    )
    _queue_schedule_validation(errors)
    return render_template('reports/schedules/index.html', payload=payload)


@permission_required('reports.manage_schedules')
def toggle_schedule(schedule_id: int) -> ResponseReturnValue:
    success, message = toggle_report_schedule(schedule_id)
    _record_schedule_feedback(
        event_type='report_schedule_toggle',
        success=success,
        title='Report Schedule Status Updated' if success else 'Report Schedule Status Update Failed',
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
        title='Report Schedule Deleted' if success else 'Report Schedule Deletion Failed',
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
        title='Report Schedule Queued' if success else 'Report Schedule Execution Failed',
        message=message,
        schedule_id=schedule_id,
        report_id=report_id,
    )
    if success and report_id is not None:
        return redirect(url_for('reports.generated_reports', focus=report_id, period='all'))
    return redirect(url_for('reports.schedules'))
