from flask import redirect, request, send_file, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.extensions.db import db
from app.models.report import Report
from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.export.artifacts import get_report_artifact_format
from app.reports.export.service import generate_report_artifact, get_download_file_path


@permission_required('reports.generate')
def generate_report_output(report_id: int) -> ResponseReturnValue:
    report = db.session.get(Report, report_id)
    artifact_format = get_report_artifact_format(report.output_format if report else 'pdf')
    success, message = generate_report_artifact(report_id)
    detail_url = url_for('reports.generated_report_detail', report_id=report_id)

    record_operational_activity(
        user_id=current_user.id,
        event_type='report_artifact_generation',
        status='success' if success else 'error',
        title=(
            f'Report {artifact_format.label} Generated'
            if success
            else f'Report {artifact_format.label} Generation Failed'
        ),
        message=message,
        action_url=detail_url,
        action_label='View report',
        action_icon='file-text',
        metadata={
            'report_id': report_id,
            'output_format': artifact_format.value,
            'outcome': 'success' if success else 'failed',
        },
        queue_feedback=True,
    )

    next_url = request.form.get('next', '')
    if next_url.startswith('/reports/generated'):
        return redirect(next_url)
    return redirect(detail_url)


@permission_required('reports.generate')
def generate_report_pdf(report_id: int) -> ResponseReturnValue:
    """Backward-compatible route handler for historical form actions."""

    return generate_report_output(report_id)


@permission_required('reports.view')
def download_report_artifact(report_id: int) -> ResponseReturnValue:
    report = db.session.get(Report, report_id)
    artifact_format = get_report_artifact_format(report.output_format if report else 'pdf')
    success, message, file_path = get_download_file_path(report_id)

    if not success or file_path is None:
        detail_url = url_for('reports.generated_report_detail', report_id=report_id)
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


@permission_required('reports.view')
def download_report_pdf(report_id: int) -> ResponseReturnValue:
    """Backward-compatible download handler."""

    return download_report_artifact(report_id)
