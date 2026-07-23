from flask import redirect, request, send_file, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.export.service import generate_pdf_for_report, get_download_file_path


@permission_required('reports.generate')
def generate_report_pdf(report_id: int) -> ResponseReturnValue:
    success, message = generate_pdf_for_report(report_id)
    detail_url = url_for('reports.generated_report_detail', report_id=report_id)

    record_operational_activity(
        user_id=current_user.id,
        event_type='report_pdf_generation',
        status='success' if success else 'error',
        title='Report PDF Generated' if success else 'Report PDF Generation Failed',
        message=message,
        action_url=detail_url,
        action_label='View report',
        action_icon='file-text',
        metadata={'report_id': report_id, 'outcome': 'success' if success else 'failed'},
        queue_feedback=True,
    )

    next_url = request.form.get('next', '')
    if next_url.startswith('/reports/generated'):
        return redirect(next_url)
    return redirect(detail_url)


@permission_required('reports.view')
def download_report_pdf(report_id: int) -> ResponseReturnValue:
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
        mimetype='application/pdf',
    )
