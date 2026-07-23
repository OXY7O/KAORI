import logging

from flask import redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.storage.service import (
    build_report_cleanup_dry_run,
    get_report_storage_payload,
    scan_report_storage_integrity,
    verify_active_report_storage,
)

logger = logging.getLogger(__name__)


@permission_required('reports.manage_storage')
def storage() -> ResponseReturnValue:
    if request.args.get('cleanup_dry_run') == '1':
        payload = get_report_storage_payload()
        payload['cleanup_dry_run_result'] = build_report_cleanup_dry_run()
        return render_template('reports/storage/index.html', payload=payload)

    if request.args.get('integrity') == '1':
        payload = get_report_storage_payload()
        payload['integrity_result'] = scan_report_storage_integrity()
        return render_template('reports/storage/index.html', payload=payload)

    if request.args.get('verify') == '1':
        status = 'error'
        title = 'Report Storage Verification Failed'
        message = 'KAORI could not verify the active report storage backend.'
        detail = None
        metadata: dict[str, object] = {'outcome': 'failed'}

        try:
            result = verify_active_report_storage()
        except Exception as exc:
            logger.exception('Report storage verification failed.')
            detail = str(exc)
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
            action_url=url_for('reports.storage'),
            action_label='View storage',
            action_icon='hard-drive',
            metadata=metadata,
            queue_feedback=True,
        )
        return redirect(url_for('reports.storage'))

    payload = get_report_storage_payload()
    return render_template('reports/storage/index.html', payload=payload)
