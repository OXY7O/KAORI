import logging

from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.web import render_reports_unavailable
from app.reports.generated.service import (
    archive_report_record,
    bulk_archive_report_records,
    get_generated_reports_payload,
    get_report_detail_payload,
    restore_archived_report_record,
)


logger = logging.getLogger(__name__)


def _current_user_id() -> int:
    return int(getattr(current_user, 'id', 0) or 0)


def _record_archive_feedback(
    *,
    event_type: str,
    success: bool,
    title: str,
    message: str,
    action_url: str,
    metadata: dict[str, object],
) -> None:
    record_operational_activity(
        user_id=_current_user_id(),
        event_type=event_type,
        status='success' if success else 'error',
        title=title,
        message=message,
        action_url=action_url,
        action_label='View generated reports',
        metadata={**metadata, 'outcome': 'success' if success else 'failed'},
        queue_feedback=True,
    )


@permission_required('reports.view')
def generated_reports() -> ResponseReturnValue:
    try:
        payload = get_generated_reports_payload(request.args)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Generated Reports could not be loaded.')
        return render_reports_unavailable(
            page_title='Generated Reports',
            description='Review generated report records and stored artifacts.',
            reason='KAORI could not load the generated report registry. The active storage backend or another reporting dependency may be unavailable.',
            retry_url=url_for('reports.generated_reports'),
        )
    return render_template('reports/generated/index.html', payload=payload)


@permission_required('reports.view')
def generated_report_detail(report_id: int) -> ResponseReturnValue:
    try:
        payload = get_report_detail_payload(report_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Generated report detail could not be loaded for report_id=%s.', report_id)
        return render_reports_unavailable(
            page_title='Report Detail',
            description='Review report metadata and artifact availability.',
            reason='KAORI could not load this report detail. The report record remains protected while storage connectivity is reviewed.',
            retry_url=url_for('reports.generated_report_detail', report_id=report_id),
        )
    return render_template('reports/generated/detail.html', payload=payload)


@permission_required('reports.manage_storage')
def bulk_archive_generated_reports() -> ResponseReturnValue:
    report_ids = [int(report_id) for report_id in request.form.getlist('report_ids') if report_id.isdigit()]
    success, message = bulk_archive_report_records(report_ids)
    _record_archive_feedback(
        event_type='generated_reports_bulk_archive',
        success=success,
        title='Generated reports archived' if success else 'Generated reports archive failed',
        message=message,
        action_url=url_for('reports.generated_reports'),
        metadata={'requested_report_count': len(report_ids)},
    )

    next_url = request.form.get('next', '')
    if next_url.startswith('/reports/generated'):
        return redirect(next_url)
    return redirect(url_for('reports.generated_reports'))


@permission_required('reports.manage_storage')
def archive_generated_report(report_id: int) -> ResponseReturnValue:
    success, message = archive_report_record(report_id)
    _record_archive_feedback(
        event_type='generated_report_archive',
        success=success,
        title='Generated report archived' if success else 'Generated report archive failed',
        message=message,
        action_url=url_for('reports.generated_report_detail', report_id=report_id),
        metadata={'report_id': report_id},
    )

    next_url = request.form.get('next', '')
    if next_url.startswith('/reports/generated'):
        return redirect(next_url)
    return redirect(url_for('reports.generated_report_detail', report_id=report_id))


@permission_required('reports.manage_storage')
def restore_generated_report(report_id: int) -> ResponseReturnValue:
    success, message = restore_archived_report_record(report_id)
    _record_archive_feedback(
        event_type='generated_report_restore',
        success=success,
        title='Generated report restored' if success else 'Generated report restore failed',
        message=message,
        action_url=url_for('reports.generated_report_detail', report_id=report_id),
        metadata={'report_id': report_id},
    )

    next_url = request.form.get('next', '')
    if next_url.startswith('/reports/generated'):
        return redirect(next_url)
    return redirect(url_for('reports.generated_report_detail', report_id=report_id))
