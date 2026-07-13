from __future__ import annotations

from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from app.notifications.service import (
    get_navigation_notification_context,
    get_notification_activity_context,
    mark_all_notifications_read,
    mark_notification_read,
    record_operational_activity,
)
from app.rbac.decorators import permission_required
from app.retention.presentation import build_activity_retention_context
from app.retention.service import get_archive_download_path, verify_archive_artifact

notifications_bp = Blueprint(
    'notifications',
    __name__,
    url_prefix='/notifications',
)


def _request_int(
    name: str,
    default: int,
) -> int:
    try:
        return int(request.args.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _render_notification_center() -> str:
    context = get_navigation_notification_context(
        user_id=current_user.id,
    )

    return render_template(
        'components/navigation/_notification_center.html',
        navigation_notifications=context['items'],
        navigation_unread_count=context['unread_count'],
        navigation_total_count=context['total_count'],
        navigation_display_limit=context['display_limit'],
        notification_oob=False,
    )


@notifications_bp.get('/panel')
@login_required
def panel() -> ResponseReturnValue:
    return _render_notification_center()


@notifications_bp.get('/activity')
@permission_required('settings.view_operational_activity')
def activity_log() -> ResponseReturnValue:
    context = get_notification_activity_context(
        user_id=_request_int('user_id', 0) or None,
        page=_request_int('page', 1),
        per_page=_request_int('per_page', 5),
        status=request.args.get('status', 'all'),
        event_type=request.args.get('event_type', 'all'),
        read_state=request.args.get('read_state', 'all'),
        search=request.args.get('search', ''),
    )

    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'notifications/partials/_activity_table_content.html',
            **context,
        )

    context['retention'] = build_activity_retention_context(
        include_preview=request.args.get('retention_preview') == '1',
        archive_page=_request_int('archive_page', 1),
        archive_per_page=_request_int('archive_per_page', 5),
    )

    return render_template(
        'notifications/activity.html',
        **context,
    )


@notifications_bp.post('/activity/retention/run')
@permission_required('settings.manage_operational_activity_retention')
def run_activity_retention() -> ResponseReturnValue:
    mode = request.form.get('mode', 'archive_only').strip().lower()
    if mode not in {'archive_only', 'archive_and_cleanup'}:
        flash('Unsupported retention operation.', 'error')
        return redirect(url_for('notifications.activity_log') + '#activity-retention')

    cleanup = mode == 'archive_and_cleanup'
    try:
        async_result = current_app.extensions['celery'].send_task(
            'app.retention.tasks.run_domain_retention',
            kwargs={
                'domain_name': 'operational_activity',
                'cleanup': cleanup,
                'trigger_type': 'manual',
                'requested_by_user_id': current_user.id,
            },
            queue=current_app.config.get('RETENTION_CELERY_QUEUE', 'inventory'),
        )
        record_operational_activity(
            user_id=current_user.id,
            event_type='operational_activity_retention_requested',
            status='info',
            title='Activity retention queued',
            message=(
                'Archive and cleanup was queued for background execution.'
                if cleanup
                else 'Archive-only retention was queued for background execution.'
            ),
            detail='The worker will create and verify the archive before any cleanup can begin.',
            action_url=url_for('notifications.activity_log') + '#activity-retention',
            metadata={
                'task_id': async_result.id,
                'operation_mode': mode,
                'domain': 'operational_activity',
            },
        )
        flash('Retention job queued. Refresh the archive registry to review progress.', 'success')
    except Exception as exc:
        current_app.logger.exception('Could not queue operational activity retention.')
        flash(f'Retention job could not be queued: {type(exc).__name__}.', 'error')

    return redirect(url_for('notifications.activity_log') + '#activity-retention')


@notifications_bp.post('/activity/archives/<archive_id>/verify')
@permission_required('settings.manage_operational_activity_retention')
def verify_activity_archive(archive_id: str) -> ResponseReturnValue:
    try:
        result = verify_archive_artifact(archive_id)
        record_operational_activity(
            user_id=current_user.id,
            event_type='operational_activity_archive_verified',
            status='success',
            title='Activity archive verified',
            message='Archive checksum and stored object size were verified successfully.',
            detail='The verification used the archive registry checksum and the configured archive storage backend.',
            action_url=url_for('notifications.activity_log') + '#activity-retention',
            metadata={
                'archive_id': archive_id,
                'checksum_sha256': result.get('checksum_sha256'),
                'size_bytes': result.get('size_bytes'),
            },
        )
        flash('Archive verification completed successfully.', 'success')
    except Exception as exc:
        current_app.logger.exception('Activity archive verification failed for %s.', archive_id)
        flash(f'Archive verification failed: {exc}', 'error')

    return redirect(url_for('notifications.activity_log') + '#activity-retention')


@notifications_bp.get('/activity/archives/<archive_id>/download')
@permission_required('settings.export_operational_activity')
def download_activity_archive(archive_id: str) -> ResponseReturnValue:
    kind = request.args.get('kind', 'data').strip().lower()
    if kind not in {'data', 'manifest'}:
        kind = 'data'

    try:
        artifact, download_path = get_archive_download_path(
            archive_id,
            kind=kind,
        )
        record_operational_activity(
            user_id=current_user.id,
            event_type='operational_activity_archive_downloaded',
            status='success',
            title='Activity archive downloaded',
            message=f'The activity archive {kind} file was downloaded.',
            detail='Archive downloads are recorded because operational activity exports may contain sensitive administrative context.',
            action_url=url_for('notifications.activity_log') + '#activity-retention',
            metadata={
                'archive_id': artifact.id,
                'download_kind': kind,
                'storage_backend': artifact.storage_backend,
            },
        )
        return send_file(
            download_path,
            as_attachment=True,
            download_name=Path(download_path).name,
            mimetype='application/json' if kind == 'manifest' else 'application/gzip',
        )
    except Exception as exc:
        current_app.logger.exception('Could not download activity archive %s.', archive_id)
        flash(f'Archive download failed: {exc}', 'error')
        return redirect(url_for('notifications.activity_log') + '#activity-retention')


@notifications_bp.post('/<int:notification_id>/read')
@login_required
def mark_read(notification_id: int) -> ResponseReturnValue:
    mark_notification_read(
        notification_id=notification_id,
        user_id=current_user.id,
    )

    return _render_notification_center()


@notifications_bp.post('/read-all')
@login_required
def mark_all_read() -> ResponseReturnValue:
    mark_all_notifications_read(
        user_id=current_user.id,
    )

    return _render_notification_center()
