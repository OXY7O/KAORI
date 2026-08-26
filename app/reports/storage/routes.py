import logging

from flask import make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.access.rbac.decorators import permission_required
from app.platform_operations.notifications.service import record_operational_activity
from app.reports.storage.jobs import (
    ReportStorageVerificationEnqueueError,
    enqueue_report_storage_verification,
)
from app.reports.storage.service import (
    build_storage_integrity_presentation,
    get_report_storage_payload,
    normalize_storage_workspace,
    scan_report_storage_integrity,
)
from app.reports.storage.verification import get_report_storage_verification_presentation
from app.reports.web import render_reports_unavailable

logger = logging.getLogger(__name__)


@permission_required('reports.manage_storage')
def storage() -> ResponseReturnValue:
    workspace = normalize_storage_workspace(request.args.get('workspace'))
    try:
        payload = get_report_storage_payload(workspace=workspace)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Reports Storage could not be loaded.')
        return render_reports_unavailable(
            page_title='Reports Storage',
            description='Review artifact backend, integrity, and lifecycle governance.',
            reason='KAORI could not inspect the active report storage backend. Configuration remains unchanged while connectivity is restored.',
            retry_url=url_for('reports.storage'),
        )
    return render_template('reports/storage/index.html', payload=payload)


@permission_required('reports.manage_storage')
def verify_storage() -> ResponseReturnValue:
    workspace = normalize_storage_workspace(request.form.get('workspace'))
    try:
        outcome = enqueue_report_storage_verification(
            requested_by_user_id=int(current_user.id),
        )
    except ReportStorageVerificationEnqueueError:
        logger.exception('Report storage verification dispatch failed.')
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='report_storage_verification',
            status='error',
            title='Report Storage Verification Could Not Start',
            message='KAORI could not dispatch strong storage verification to the worker.',
            detail='Review Celery broker and report-storage worker availability, then retry.',
            action_url=url_for('reports.storage', workspace='integrity'),
            action_label='View storage',
            action_icon='hard-drive',
            metadata={'outcome': 'dispatch_failed'},
            queue_feedback=True,
        )
    else:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='report_storage_verification',
            status='success' if outcome.created else 'info',
            title=(
                'Report Storage Verification Queued'
                if outcome.created
                else 'Report Storage Verification Already Active'
            ),
            message=outcome.message,
            detail=(
                'The report-storage worker owns provider connectivity, write confirmation, cleanup, '
                'and technical traceback evidence.'
            ),
            action_url=url_for('reports.storage', workspace='integrity'),
            action_label='View verification',
            action_icon='hard-drive',
            metadata={
                'outcome': outcome.status,
                'job_execution_id': outcome.job.id,
                'job_public_id': outcome.job.public_id,
                'created': outcome.created,
            },
            queue_feedback=True,
        )
    return redirect(url_for('reports.storage', workspace=workspace))


@permission_required('reports.manage_storage')
def storage_verification_status() -> ResponseReturnValue:
    verification_execution = get_report_storage_verification_presentation()
    response = make_response(
        render_template(
            'reports/storage/_verification_status.html',
            verification_execution=verification_execution,
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@permission_required('reports.manage_storage')
def scan_storage_integrity() -> ResponseReturnValue:
    try:
        payload = get_report_storage_payload(workspace='integrity')
        if payload['integrity_actions_enabled']:
            payload['integrity_result'] = build_storage_integrity_presentation(scan_report_storage_integrity())
    except Exception:
        logger.exception('Report storage integrity scan failed.')
        return render_reports_unavailable(
            page_title='Reports Storage',
            description='Review artifact backend, integrity, and lifecycle governance.',
            reason='KAORI could not complete the artifact integrity scan. No report artifacts were changed.',
            retry_url=url_for('reports.storage', workspace='integrity'),
        )
    return render_template('reports/storage/index.html', payload=payload)
