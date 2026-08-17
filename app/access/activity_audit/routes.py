from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue

from app.access.activity_audit.service import build_activity_audit_context, get_activity_audit_detail
from app.rbac.decorators import permission_required

bp = Blueprint('activity_audit', __name__)


def _request_int(name: str, default: int) -> int:
    raw_value = request.args.get(name, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


@bp.get('/')
@permission_required('activity_audit.view')
def index() -> ResponseReturnValue:
    is_htmx = request.headers.get('HX-Request') == 'true'
    context = build_activity_audit_context(
        actor_key=request.args.get('actor_key'),
        page=_request_int('page', 1),
        per_page=_request_int('per_page', 5),
        status=request.args.get('status', 'all'),
        category=request.args.get('category', 'all'),
        time_range=request.args.get('time_range', '7d'),
        search=request.args.get('search', ''),
        include_summary=not is_htmx,
    )
    if is_htmx:
        return render_template('access/activity_audit/partials/_activity_table_card.html', **context)
    return render_template('access/activity_audit/index.html', **context)


@bp.get('/<int:notification_id>/details')
@permission_required('activity_audit.view')
def detail(notification_id: int) -> ResponseReturnValue:
    item = get_activity_audit_detail(notification_id=notification_id)
    if item is None:
        return ('Activity not found.', 404)
    return render_template('access/activity_audit/partials/_activity_detail.html', item=item)
