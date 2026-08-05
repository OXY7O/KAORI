import logging

from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.extensions.db import db
from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.generate.service import (
    create_report_request,
    get_form_state_from_form,
    get_generate_report_payload,
)
from app.reports.jobs.service import ReportJobEnqueueError, enqueue_report_generation
from app.reports.reference import build_report_reference
from app.reports.web import render_reports_unavailable


logger = logging.getLogger(__name__)


@permission_required('reports.generate')
def generate_report() -> ResponseReturnValue:
    if request.method == 'POST':
        user_id = getattr(current_user, 'id', None)
        success, errors, report = create_report_request(request.form, user_id)

        if success and report is not None:
            detail_url = url_for('reports.generated_report_detail', report_id=report.id)
            try:
                dispatch = enqueue_report_generation(
                    report,
                    requested_by_user_id=user_id,
                    trigger_type='manual',
                )
            except ReportJobEnqueueError:
                logger.exception('Report request %s could not be queued.', report.id)
                db.session.rollback()
                failed_report = db.session.get(type(report), report.id)
                if failed_report is not None:
                    failed_report.status = 'failed'
                    failed_report.error_message = (
                        'KAORI could not queue this report. Review the Reports worker, broker, '
                        'and queue configuration before retrying.'
                    )
                    db.session.commit()
                record_operational_activity(
                    user_id=current_user.id,
                    event_type='report_generation_queue_failed',
                    status='error',
                    title='Report Generation Not Queued',
                    message='The report request was saved, but the Reports worker could not accept the job.',
                    detail=f'Report reference: {build_report_reference(report)}.',
                    action_url=detail_url,
                    action_label='Review report',
                    action_icon='triangle-alert',
                    metadata={'report_id': report.id, 'report_type': report.report_type},
                    queue_feedback=True,
                )
                return redirect(detail_url)

            record_operational_activity(
                user_id=current_user.id,
                event_type='report_generation_queued',
                status='success',
                title='Report Generation Queued',
                message=dispatch.message,
                detail=f'Report reference: {build_report_reference(report)}.',
                action_url=detail_url,
                action_label='View report',
                action_icon='file-text',
                metadata={
                    'report_id': report.id,
                    'report_type': report.report_type,
                    'job_execution_id': dispatch.job.id if dispatch.job is not None else None,
                    'job_public_id': dispatch.job.public_id if dispatch.job is not None else None,
                    'dispatch_status': dispatch.status,
                },
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
    try:
        payload = get_generate_report_payload(form_state=form_state)
    except HTTPException:
        raise
    except ReportJobEnqueueError:
        logger.exception('Generate Report workspace could not be loaded.')
        return render_reports_unavailable(
            page_title='Generate Report',
            description='Build a governed report from connected KAORI data sources.',
            reason='KAORI could not prepare the report builder. Verify database, integration, and report storage readiness before retrying.',
            retry_url=url_for('reports.generate_report'),
        )
    return render_template('reports/generate/index.html', payload=payload)
