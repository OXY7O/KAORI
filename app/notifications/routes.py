from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from app.notifications.service import (
    get_navigation_notification_context,
    get_notification_activity_context,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.rbac.decorators import permission_required

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

    return render_template(
        'notifications/activity.html',
        **context,
    )


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
