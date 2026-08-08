from __future__ import annotations

from flask import Blueprint, jsonify, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from app.notifications.constants import ACTIVITY_CENTER_PAGE_LIMIT
from app.notifications.service import (
    get_navigation_notification_context,
    get_notification_activity_context,
    get_notification_center_page_context,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.rbac.decorators import permission_required

notifications_bp = Blueprint(
    'notifications',
    __name__,
    url_prefix='/notifications',
)

_ALLOWED_CENTER_VIEWS = frozenset({'activity', 'notifications'})


def _request_int(
    name: str,
    default: int,
) -> int:
    try:
        return int(request.args.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _center_view() -> str:
    requested_view = request.args.get('view', 'notifications').strip().lower()
    return requested_view if requested_view in _ALLOWED_CENTER_VIEWS else 'notifications'


def _navigation_context() -> dict[str, object]:
    return get_navigation_notification_context(
        user_id=current_user.id,
        include_all_jobs=current_user.has_permission('jobs.view'),
    )


def _fragment_response(template_name: str, **context: object) -> ResponseReturnValue:
    response = make_response(render_template(template_name, **context))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


def _render_notifications_panel(*, emit_oob: bool = True) -> ResponseReturnValue:
    return _fragment_response(
        'notifications/partials/_notification_deck_notifications.html',
        activity_center=_navigation_context(),
        emit_oob=emit_oob,
    )


def _render_status_snapshot() -> ResponseReturnValue:
    """Return one database snapshot; never wait for queued workers to finish."""
    context = _navigation_context()
    response = jsonify(
        {
            'active_count': int(context.get('active_count', 0)),
            'unread_count': int(context.get('unread_count', 0)),
            'activity_html': render_template(
                'notifications/partials/_notification_deck_activity_jobs.html',
                activity_center=context,
            ),
            'notifications_html': render_template(
                'notifications/partials/_notification_deck_notifications.html',
                activity_center=context,
                emit_oob=False,
            ),
        }
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


def _center_page_context() -> dict[str, object]:
    return get_notification_center_page_context(
        user_id=current_user.id,
        page=_request_int('page', 1),
        per_page=_request_int('per_page', 5),
        job_limit=ACTIVITY_CENTER_PAGE_LIMIT,
        include_all_jobs=current_user.has_permission('jobs.view'),
        status=request.args.get('status', 'all'),
        read_state=request.args.get('read_state', 'all'),
        category=request.args.get('category', 'all'),
        search=request.args.get('search', ''),
    )


def _render_center_page_content() -> str:
    context = _center_page_context()
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
            response.headers['Cache-Control'] = 'no-store, max-age=0'
            return response
        return _render_notifications_panel()

    next_url = (request.form.get('next') or request.referrer or '').strip()
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('notifications.center')
    return redirect(next_url)


@notifications_bp.get('/')
@login_required
def center() -> ResponseReturnValue:
    context = _center_page_context()
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


@notifications_bp.get('/panel/snapshot')
@login_required
def panel_snapshot() -> ResponseReturnValue:
    return _render_status_snapshot()


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
