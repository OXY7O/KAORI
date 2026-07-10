from __future__ import annotations

from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from app.notifications.service import (
    get_navigation_notification_context,
    mark_all_notifications_read,
    mark_notification_read,
)


notifications_bp = Blueprint(
    'notifications',
    __name__,
    url_prefix='/notifications',
)


def _render_notification_center() -> str:
    context = get_navigation_notification_context(
        user_id=current_user.id,
    )

    return render_template(
        'components/navigation/_notification_center.html',
        navigation_notifications=context['items'],
        navigation_unread_count=context['unread_count'],
        notification_oob=False,
    )


@notifications_bp.get('/panel')
@login_required
def panel() -> ResponseReturnValue:
    return _render_notification_center()


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
