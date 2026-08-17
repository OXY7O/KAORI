import logging

from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.access.rbac.decorators import permission_required
from app.platform_operations.notifications.service import record_operational_activity
from app.reports.storage.service import (
    build_storage_integrity_presentation,
    clear_report_storage_status_cache,
    get_report_storage_payload,
    normalize_storage_workspace,
    scan_report_storage_integrity,
    verify_active_report_storage,
)
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
    status = 'error'
    title = 'Report Storage Verification Failed'
    message = 'KAORI could not verify the active report storage backend.'
    detail = None
    metadata: dict[str, object] = {'outcome': 'failed'}

    try:
        clear_report_storage_status_cache(include_shared=True)
        result = verify_active_report_storage()
    except Exception:
        logger.exception('Report storage verification failed.')
        detail = 'The active report storage backend did not respond. Review its endpoint, credentials, and network connectivity.'
    else:
        backend = result.get('backend')
        verified = bool(result.get('verified'))
        metadata.update({'backend': backend, 'verified': verified})
        if verified:
            status = 'success'
            title = 'Report Storage Verified'
            message = f'KAORI verified the {backend} report storage backend.'
            detail = 'The active backend accepted and confirmed the verification object.'
            metadata['outcome'] = 'success'
        else:
            status = 'warning'
            title = 'Report Storage Verification Incomplete'
            message = 'KAORI completed the storage check, but could not confirm the verification object.'
            metadata['outcome'] = 'incomplete'

    record_operational_activity(
        user_id=current_user.id,
        event_type='report_storage_verification',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('reports.storage', workspace=workspace),
        action_label='View storage',
        action_icon='hard-drive',
        metadata=metadata,
        queue_feedback=True,
    )
    return redirect(url_for('reports.storage', workspace=workspace))


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
