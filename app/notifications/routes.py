from __future__ import annotations

from flask import Blueprint, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from app.notifications.constants import ACTIVITY_CENTER_PAGE_LIMIT
from app.notifications.service import (
    get_activity_center_context,
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

_ALLOWED_CENTER_VIEWS = frozenset({'running', 'attention', 'history'})


def _request_int(
    name: str,
    default: int,
) -> int:
    try:
        return int(request.args.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _center_view() -> str:
    requested_view = request.args.get('view', 'running').strip().lower()
    return requested_view if requested_view in _ALLOWED_CENTER_VIEWS else 'running'


def _render_notification_center() -> str:
    context = get_navigation_notification_context(
        user_id=current_user.id,
        include_all_jobs=current_user.has_permission('jobs.view'),
    )

    return render_template(
        'components/navigation/_notification_center.html',
        activity_center=context,
    )


def _render_center_page_content() -> str:
    context = get_activity_center_context(
        user_id=current_user.id,
        job_limit=ACTIVITY_CENTER_PAGE_LIMIT,
        notification_limit=ACTIVITY_CENTER_PAGE_LIMIT,
        include_all_jobs=current_user.has_permission('jobs.view'),
    )
    return render_template(
        'notifications/partials/_center_page_content.html',
        activity_center=context,
        selected_view=_center_view(),
    )


def _render_mutation_response() -> ResponseReturnValue:
    surface = request.args.get('surface', 'panel').strip().lower()
    if request.headers.get('HX-Request') == 'true':
        if surface == 'page':
            response = make_response(_render_center_page_content())
            response.headers['HX-Trigger-After-Swap'] = 'kaori:notifications-changed'
            return response
        return _render_notification_center()

    next_url = (request.form.get('next') or request.referrer or '').strip()
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('notifications.center')
    return redirect(next_url)


@notifications_bp.get('/')
@login_required
def center() -> ResponseReturnValue:
    context = get_activity_center_context(
        user_id=current_user.id,
        job_limit=ACTIVITY_CENTER_PAGE_LIMIT,
        notification_limit=ACTIVITY_CENTER_PAGE_LIMIT,
        include_all_jobs=current_user.has_permission('jobs.view'),
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'notifications/partials/_center_page_content.html',
            activity_center=context,
            selected_view=_center_view(),
        )
    return render_template(
        'notifications/index.html',
        activity_center=context,
        selected_view=_center_view(),
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
    return _render_mutation_response()


@notifications_bp.post('/read-all')
@login_required
def mark_all_read() -> ResponseReturnValue:
    mark_all_notifications_read(
        user_id=current_user.id,
    )
    return _render_mutation_response()
