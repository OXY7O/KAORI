import logging

from flask import (
    abort,
    redirect,
    request,
    send_file,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.authentication.session import safe_next_url
from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.models.report import Report
from app.platform_operations.notifications.service import queue_transient_feedback, record_operational_activity
from app.reports.export.artifacts import get_report_artifact_format
from app.reports.export.service import get_download_file_path
from app.reports.jobs.service import ReportJobEnqueueError, enqueue_report_generation

logger = logging.getLogger(__name__)


def _generated_registry_return_url(value: object) -> str:
    candidate = safe_next_url(value)
    if candidate == '/reports/generated' or (candidate and candidate.startswith('/reports/generated?')):
        return candidate
    return url_for('reports.generated_reports')


def _generated_detail_url(report_id: int, registry_return_url: str) -> str:
    return url_for(
        'reports.generated_report_detail',
        report_id=report_id,
        next=registry_return_url,
    )


@permission_required('reports.generate')
def generate_report_output(report_id: int) -> ResponseReturnValue:
    report = db.session.get(Report, report_id)
    if report is None:
        abort(404)

    registry_return_url = _generated_registry_return_url(request.form.get('next'))
    detail_url = _generated_detail_url(report_id, registry_return_url)
    artifact_format = get_report_artifact_format(report.output_format)
    if report.status not in {'requested', 'failed', 'ready'}:
        queue_transient_feedback(
            status='error',
            title='Report Generation Not Available',
            message=f'The report cannot be queued while its status is {report.status}.',
            action_url=detail_url,
            action_label='View report',
            action_icon='file-text',
        )
        return redirect(detail_url)

    try:
        dispatch = enqueue_report_generation(
            report,
            requested_by_user_id=getattr(current_user, 'id', None),
            trigger_type='manual',
        )
    except ReportJobEnqueueError:
        logger.exception('Report %s could not be queued for artifact generation.', report_id)
        db.session.rollback()
        failed_report = db.session.get(Report, report_id)
        if failed_report is not None and failed_report.status != 'ready':
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
            title=f'{artifact_format.label} Generation Not Queued',
            message='The report request remains available, but the Reports worker could not accept the job.',
            action_url=detail_url,
            action_label='View report',
            action_icon='triangle-alert',
            metadata={'report_id': report_id, 'output_format': artifact_format.value},
            queue_feedback=True,
        )
        return redirect(detail_url)

    record_operational_activity(
        user_id=current_user.id,
        event_type='report_generation_queued',
        status='success',
        title=f'{artifact_format.label} Generation Queued',
        message=dispatch.message,
        action_url=detail_url,
        action_label='View report',
        action_icon='file-text',
        metadata={
            'report_id': report_id,
            'output_format': artifact_format.value,
            'job_execution_id': dispatch.job.id if dispatch.job is not None else None,
            'job_public_id': dispatch.job.public_id if dispatch.job is not None else None,
            'dispatch_status': dispatch.status,
        },
        queue_feedback=True,
    )

    return redirect(detail_url)


@permission_required('reports.view')
def download_report_artifact(report_id: int) -> ResponseReturnValue:
    report = db.session.get(Report, report_id)
    if report is None:
        abort(404)
    artifact_format = get_report_artifact_format(report.output_format)
    success, message, file_path = get_download_file_path(report_id)

    if not success or file_path is None:
        registry_return_url = _generated_registry_return_url(request.args.get('next'))
        detail_url = _generated_detail_url(report_id, registry_return_url)
        queue_transient_feedback(
            status='error',
            title='Report Download Unavailable',
            message=message,
            action_url=detail_url,
            action_label='View report',
            action_icon='file-text',
        )
        return redirect(detail_url)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_path.name,
        mimetype=artifact_format.mimetype,
    )
