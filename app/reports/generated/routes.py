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

from app.access.authentication.session import safe_next_url
from app.access.rbac.decorators import permission_required
from app.platform_operations.notifications.service import record_operational_activity
from app.reports.generated.service import (
    archive_report_record,
    bulk_archive_report_records,
    get_generated_reports_payload,
    get_report_detail_payload,
    restore_archived_report_record,
)
from app.reports.web import render_reports_unavailable

logger = logging.getLogger(__name__)


def _current_user_id() -> int:
    return int(getattr(current_user, 'id', 0) or 0)


def _generated_registry_return_url(value: object) -> str:
    candidate = safe_next_url(value)
    if candidate == '/reports/generated' or (candidate and candidate.startswith('/reports/generated?')):
        return candidate
    return url_for('reports.generated_reports')


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
            description='Review generated report records and stored artifacts with governed recovery evidence in KAORI.',
            reason='KAORI could not load the generated report registry. The active storage backend or another reporting dependency may be unavailable.',
            retry_url=url_for('reports.generated_reports'),
        )
    return render_template('reports/generated/index.html', payload=payload)


@permission_required('reports.view')
def generated_report_detail(report_id: int) -> ResponseReturnValue:
    registry_return_url = _generated_registry_return_url(request.args.get('next'))
    try:
        payload = get_report_detail_payload(report_id)
        payload['registry_return_url'] = registry_return_url
    except HTTPException:
        raise
    except Exception:
        logger.exception('Generated report detail could not be loaded for report_id=%s.', report_id)
        return render_reports_unavailable(
            page_title='Report Detail',
            description='Review report metadata and artifact availability with governed recovery evidence in KAORI.',
            reason='KAORI could not load this report detail. The report record remains protected while storage connectivity is reviewed.',
            retry_url=url_for(
                'reports.generated_report_detail',
                report_id=report_id,
                next=registry_return_url,
            ),
        )
    return render_template('reports/generated/detail.html', payload=payload)


@permission_required('reports.manage_storage')
def bulk_archive_generated_reports() -> ResponseReturnValue:
    registry_return_url = _generated_registry_return_url(request.form.get('next'))
    report_ids = [int(report_id) for report_id in request.form.getlist('report_ids') if report_id.isdigit()]
    success, message = bulk_archive_report_records(report_ids)
    _record_archive_feedback(
        event_type='generated_reports_bulk_archive',
        success=success,
        title='Generated reports archived' if success else 'Generated reports archive failed',
        message=message,
        action_url=registry_return_url,
        metadata={'requested_report_count': len(report_ids)},
    )

    return redirect(registry_return_url)


@permission_required('reports.manage_storage')
def archive_generated_report(report_id: int) -> ResponseReturnValue:
    registry_return_url = _generated_registry_return_url(request.form.get('next'))
    detail_url = url_for(
        'reports.generated_report_detail',
        report_id=report_id,
        next=registry_return_url,
    )
    success, message = archive_report_record(report_id)
    _record_archive_feedback(
        event_type='generated_report_archive',
        success=success,
        title='Generated report archived' if success else 'Generated report archive failed',
        message=message,
        action_url=detail_url,
        metadata={'report_id': report_id},
    )
    return redirect(detail_url)


@permission_required('reports.manage_storage')
def restore_generated_report(report_id: int) -> ResponseReturnValue:
    registry_return_url = _generated_registry_return_url(request.form.get('next'))
    detail_url = url_for(
        'reports.generated_report_detail',
        report_id=report_id,
        next=registry_return_url,
    )
    success, message = restore_archived_report_record(report_id)
    _record_archive_feedback(
        event_type='generated_report_restore',
        success=success,
        title='Generated report restored' if success else 'Generated report restore failed',
        message=message,
        action_url=detail_url,
        metadata={'report_id': report_id},
    )
    return redirect(detail_url)
