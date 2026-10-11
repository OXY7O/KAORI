from __future__ import annotations

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from flask.typing import ResponseReturnValue

from app.access.activity_audit.administrative_sources import build_administrative_evidence_context
from app.access.activity_audit.service import build_activity_audit_context, get_activity_audit_detail
from app.access.activity_audit.source_links import build_related_source_links
from app.access.rbac.decorators import permission_required

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
    is_htmx = (
        request.headers.get('HX-Request') == 'true'
        and request.headers.get('HX-History-Restore-Request') != 'true'
    )
    target = request.headers.get('HX-Target') if is_htmx else None
    can_view_jobs = current_user.has_permission('jobs.view')
    can_manage_tenants = current_user.has_permission('tenant.manage')
    has_administrative_sources = can_view_jobs or can_manage_tenants
    selected_audit_tab = 'administrative' if request.args.get('view') == 'administrative' else 'activity'
    if selected_audit_tab == 'administrative' and not has_administrative_sources:
        abort(403)
    tab_context = {
        'selected_audit_tab': selected_audit_tab,
        'has_administrative_sources': has_administrative_sources,
    }
    if is_htmx and selected_audit_tab == 'administrative' and target in (
        'activity-audit-records', 'activity-administrative-evidence'
    ):
        evidence = build_administrative_evidence_context(
            scope=request.args.get('admin_scope'),
            page=_request_int('admin_page', 1),
            can_view_jobs=can_view_jobs,
            can_manage_tenants=can_manage_tenants,
        )
        if evidence is None:
            abort(403)
        tab_context['administrative_evidence'] = evidence
        if target == 'activity-administrative-evidence':
            return render_template(
                'access/activity_audit/partials/_administrative_evidence.html',
                administrative_evidence=evidence,
                embedded=True,
            )
        return render_template(
            'access/activity_audit/partials/_audit_records_workspace.html', **tab_context
        )

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
    context.update(tab_context)
    if is_htmx:
        if target == 'activity-audit-records':
            return render_template(
                'access/activity_audit/partials/_audit_records_workspace.html', **context
            )
        return render_template(
            'access/activity_audit/partials/_activity_table_card.html', embedded=True, **context
        )

    if selected_audit_tab == 'administrative':
        context['administrative_evidence'] = build_administrative_evidence_context(
            scope=request.args.get('admin_scope'),
            page=_request_int('admin_page', 1),
            can_view_jobs=can_view_jobs,
            can_manage_tenants=can_manage_tenants,
        )
    return render_template('access/activity_audit/index.html', **context)


@bp.get('/<int:notification_id>/details')
@permission_required('activity_audit.view')
def detail(notification_id: int) -> ResponseReturnValue:
    item = get_activity_audit_detail(notification_id=notification_id)
    if item is None:
        return ('Activity not found.', 404)
    item['related_sources'] = build_related_source_links(
        notification_id=notification_id,
        can_view_jobs=current_user.has_permission('jobs.view'),
        can_view_deliveries=current_user.has_permission('integrations.manage'),
        can_view_tenants=(
            current_user.has_permission('tenant.view') or current_user.has_permission('tenant.manage')
        ),
    )
    return render_template('access/activity_audit/partials/_activity_detail.html', item=item)


@bp.get('/administrative-evidence')
@permission_required('activity_audit.view')
def administrative_evidence() -> ResponseReturnValue:
    """Separate permissioned administrative register; never mix Notification rows."""
    evidence = build_administrative_evidence_context(
        scope=request.args.get('admin_scope'),
        page=_request_int('admin_page', 1),
        can_view_jobs=current_user.has_permission('jobs.view'),
        can_manage_tenants=current_user.has_permission('tenant.manage'),
    )
    if evidence is None:
        abort(403)
    if request.headers.get('HX-Request') != 'true':
        return redirect(
            url_for(
                'access.activity_audit.index',
                view='administrative',
                admin_scope=evidence['scope'],
                admin_page=evidence['pagination']['page'],
            )
        )
    response = make_response(
        render_template(
            'access/activity_audit/partials/_administrative_evidence.html',
            administrative_evidence=evidence,
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response
