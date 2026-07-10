from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.rbac.decorators import permission_required
from app.reports.schedules.service import (
    create_report_schedule,
    delete_report_schedule,
    get_form_state_from_schedule_form,
    get_report_schedules_payload,
    run_schedule_now,
    toggle_report_schedule,
    update_report_schedule,
)


@permission_required('reports.manage_schedules')
def schedules() -> ResponseReturnValue:
    payload = get_report_schedules_payload(
        request.args,
    )

    return render_template(
        'reports/schedules/index.html',
        payload=payload,
    )


@permission_required('reports.manage_schedules')
def create_schedule() -> ResponseReturnValue:
    user_id = getattr(
        current_user,
        'id',
        None,
    )

    success, errors, _schedule = create_report_schedule(
        request.form,
        user_id,
    )

    if success:
        flash(
            'Report schedule created successfully.',
            'success',
        )
        return redirect(
            url_for(
                'reports.schedules',
            )
        )

    form_state = get_form_state_from_schedule_form(
        request.form,
    )
    payload = get_report_schedules_payload(
        request.args,
        form_state=form_state,
        errors=errors,
    )

    for error in errors:
        flash(
            error,
            'error',
        )

    return render_template(
        'reports/schedules/index.html',
        payload=payload,
    )


@permission_required('reports.manage_schedules')
def update_schedule(
    schedule_id: int,
) -> ResponseReturnValue:
    success, errors = update_report_schedule(
        schedule_id,
        request.form,
    )

    if success:
        flash(
            'Report schedule updated successfully.',
            'success',
        )
    else:
        for error in errors:
            flash(
                error,
                'error',
            )

    return redirect(
        url_for(
            'reports.schedules',
        )
    )


@permission_required('reports.manage_schedules')
def toggle_schedule(
    schedule_id: int,
) -> ResponseReturnValue:
    success, message = toggle_report_schedule(
        schedule_id,
    )

    flash(
        message,
        'success' if success else 'error',
    )

    return redirect(
        url_for(
            'reports.schedules',
        )
    )


@permission_required('reports.manage_schedules')
def delete_schedule(
    schedule_id: int,
) -> ResponseReturnValue:
    success, message = delete_report_schedule(
        schedule_id,
    )

    flash(
        message,
        'success' if success else 'error',
    )

    return redirect(
        url_for(
            'reports.schedules',
        )
    )


@permission_required('reports.manage_schedules')
def run_schedule(
    schedule_id: int,
) -> ResponseReturnValue:
    success, message, report_id = run_schedule_now(
        schedule_id,
    )

    flash(
        message,
        'success' if success else 'error',
    )

    if success and report_id is not None:
        return redirect(
            url_for(
                'reports.generated_report_detail',
                report_id=report_id,
            )
        )

    return redirect(
        url_for(
            'reports.schedules',
        )
    )
