from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.generate.service import (
    create_report_request,
    get_form_state_from_form,
    get_generate_report_payload,
)


@permission_required('reports.generate')
def generate_report() -> ResponseReturnValue:
    if request.method == 'POST':
        user_id = getattr(current_user, 'id', None)
        success, errors, report = create_report_request(request.form, user_id)

        if success and report is not None:
            record_operational_activity(
                user_id=current_user.id,
                event_type='report_request_created',
                status='success',
                title='Report Request Created',
                message='KAORI created the report request. Generate the PDF from Generated Reports.',
                detail=f'Report ID: {report.id}.',
                action_url=url_for('reports.generated_report_detail', report_id=report.id),
                action_label='View report',
                action_icon='file-text',
                metadata={'report_id': report.id, 'report_type': report.report_type},
                queue_feedback=True,
            )
            return redirect(url_for('reports.generated_reports'))

        form_state = get_form_state_from_form(request.form)
        payload = get_generate_report_payload(form_state=form_state, errors=errors)
        queue_transient_feedback(
            status='error',
            title='Report Request Not Created',
            message='Review the report configuration and correct the highlighted fields.',
            detail=' '.join(errors) if errors else 'KAORI could not validate the report request.',
        )
        return render_template('reports/generate/index.html', payload=payload)

    form_state = get_form_state_from_form(request.args)
    payload = get_generate_report_payload(form_state=form_state)
    return render_template('reports/generate/index.html', payload=payload)
