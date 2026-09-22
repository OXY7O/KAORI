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

from app.access.rbac.decorators import permission_required
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import queue_transient_feedback, record_operational_activity
from app.reports.generate.service import create_report_request, get_form_state_from_form, get_generate_report_payload
from app.reports.jobs.service import ReportJobEnqueueError, enqueue_report_generation
from app.reports.reference import build_report_reference
from app.reports.repository import mark_report_queue_failure
from app.reports.web import render_reports_unavailable

logger = logging.getLogger(__name__)


@permission_required('reports.generate')
def generate_report() -> ResponseReturnValue:
    if request.method == 'POST':
        user_id = getattr(current_user, 'id', None)
        success, errors, report = create_report_request(request.form, user_id)

        if success and report is not None:
            detail_url = url_for('reports.generated_report_detail', report_id=report.id)
            generated_url = url_for('reports.generated_reports', focus=report.id, period='all')
            try:
                dispatch = enqueue_report_generation(
                    report,
                    requested_by_user_id=user_id,
                    trigger_type='manual',
                )
            except ReportJobEnqueueError:
                logger.exception('Report request %s could not be queued.', report.id)
                mark_report_queue_failure(
                    report.id,
                    message=(
                        'KAORI could not queue this report. Review the Reports worker, broker, '
                        'and queue configuration before retrying.'
                    ),
                )
                record_operational_activity(
                    user_id=current_user.id,
                    event_type='report_generation_queue_failed',
                    status='error',
                    title='Report Not Queued',
                    message=f'{report.name} was saved, but KAORI could not dispatch the generation job.',
                    detail=f'Report reference: {build_report_reference(report)}.',
                    action_url=detail_url,
                    action_label='Review report',
                    action_icon='triangle-alert',
                    metadata={
                        'report_id': report.id,
                        'report_name': report.name,
                        'report_type': report.report_type,
                        'feedback_delivery': 'toast',
                    },
                    queue_feedback=True,
                    delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE,
                )
                return redirect(detail_url)

            record_operational_activity(
                user_id=current_user.id,
                event_type='report_generation_queued',
                status='success',
                title='Report Queued',
                message=f'{report.name} was queued for artifact generation.',
                detail=f'Report reference: {build_report_reference(report)}.',
                action_url=generated_url,
                action_label='Open generated reports',
                action_icon='files',
                metadata={
                    'report_id': report.id,
                    'report_name': report.name,
                    'report_type': report.report_type,
                    'job_execution_id': dispatch.job.id if dispatch.job is not None else None,
                    'job_public_id': dispatch.job.public_id if dispatch.job is not None else None,
                    'dispatch_status': dispatch.status,
                    'feedback_delivery': 'toast',
                },
                queue_feedback=True,
                delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
            )
            return redirect(generated_url)

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
            description='Build governed reports from connected KAORI data sources safely.',
            reason='KAORI could not prepare the report builder. Verify database, integration, and report storage readiness before retrying.',
            retry_url=url_for('reports.generate_report'),
        )
    return render_template('reports/generate/index.html', payload=payload)
