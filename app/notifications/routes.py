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

from .service import (
    record_operational_activity,
    get_navigation_notification_context,
    get_notification_activity_context,
    mark_notification_read,
    mark_all_notifications_read,
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


def _retention_request_int(
    name: str,
    default: int,
) -> int:
    try:
        return int(request.values.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _build_retention_context_from_request(
    *,
    feedback: dict | None = None,
    poll_once: bool = False,
) -> dict:
    return build_activity_retention_context(
        include_preview=request.values.get('retention_preview') == '1',
        archive_page=_retention_request_int('archive_page', 1),
        archive_per_page=_retention_request_int('archive_per_page', 5),
        archive_status=request.values.get('archive_status', 'all'),
        archive_trigger=request.values.get('archive_trigger', 'all'),
        archive_mode=request.values.get('archive_mode', 'all'),
        archive_storage=request.values.get('archive_storage', 'all'),
        archive_search=request.values.get('archive_search', ''),
        feedback=feedback,
        poll_once=poll_once,
    )


def _render_activity_retention_panel(
    *,
    feedback: dict | None = None,
    poll_once: bool = False,
) -> str:
    return render_template(
        'notifications/partials/_activity_retention.html',
        retention=_build_retention_context_from_request(
            feedback=feedback,
            poll_once=poll_once,
        ),
    )


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

    context['retention'] = _build_retention_context_from_request()

    return render_template(
        'notifications/activity.html',
        **context,
    )


@notifications_bp.get('/activity/retention')
@permission_required('settings.view_operational_activity')
def activity_retention_panel() -> ResponseReturnValue:
    return _render_activity_retention_panel()


@notifications_bp.post('/activity/retention/run')
@permission_required('settings.manage_operational_activity_retention')
def run_activity_retention() -> ResponseReturnValue:
    mode = request.form.get('mode', 'archive_only').strip().lower()
    is_htmx = request.headers.get('HX-Request') == 'true'
    if mode not in {'archive_only', 'archive_and_cleanup'}:
        feedback = {
            'status': 'error',
            'title': 'Retention action rejected',
            'message': 'The requested retention operation is not supported.',
        }
        if is_htmx:
            return _render_activity_retention_panel(feedback=feedback)
        flash(feedback['message'], 'error')
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
        feedback = {
            'status': 'success',
            'title': 'Retention job queued',
            'message': (
                'Archive and cleanup is running in the background. Cleanup remains blocked until archive verification succeeds.'
                if cleanup
                else 'Archive generation is running in the background without database cleanup.'
            ),
            'detail': f'Task {async_result.id[:8]} was sent to the {current_app.config.get("RETENTION_CELERY_QUEUE", "inventory")} queue.',
        }
        if is_htmx:
            return _render_activity_retention_panel(
                feedback=feedback,
                poll_once=True,
            )
        flash(feedback['message'], 'success')
    except Exception as exc:
        current_app.logger.exception('Could not queue operational activity retention.')
        feedback = {
            'status': 'error',
            'title': 'Retention job could not be queued',
            'message': f'The background task request failed with {type(exc).__name__}.',
            'detail': 'No archive was created and no database cleanup was started.',
        }
        if is_htmx:
            return _render_activity_retention_panel(feedback=feedback)
        flash(feedback['message'], 'error')

    return redirect(url_for('notifications.activity_log') + '#activity-retention')


@notifications_bp.post('/activity/archives/<archive_id>/verify')
@permission_required('settings.manage_operational_activity_retention')
def verify_activity_archive(archive_id: str) -> ResponseReturnValue:
    is_htmx = request.headers.get('HX-Request') == 'true'
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
        feedback = {
            'status': 'success',
            'title': 'Archive verification completed',
            'message': 'The archive data and manifest match their stored size and SHA-256 checksum.',
        }
        if is_htmx:
            return _render_activity_retention_panel(feedback=feedback)
        flash(feedback['message'], 'success')
    except Exception as exc:
        current_app.logger.exception('Activity archive verification failed for %s.', archive_id)
        feedback = {
            'status': 'error',
            'title': 'Archive verification failed',
            'message': str(exc),
            'detail': 'The archive registry was kept for investigation and no cleanup was executed by this verification action.',
        }
        if is_htmx:
            return _render_activity_retention_panel(feedback=feedback)
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
