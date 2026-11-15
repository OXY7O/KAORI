"""Source Control operational product workspace, separate from GitHub setup."""

from __future__ import annotations

from flask import Blueprint, abort, make_response, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.common.pagination import paginate_sequence
from app.integrations.source_control.repository_inventory import read_installation_inventory_for_current_session
from app.integrations.source_control.uat_access import local_super_admin
from app.source_control.presentation import build_source_control_overview
from app.source_control.repository_coverage import read_repository_coverage_for_current_session

source_control_bp = Blueprint('source_control', __name__, url_prefix='/source-control')

_PAGE_SIZES = (5, 10, 25, 50)


def _require_product_uat_access() -> None:
    """Product UAT access is independent of GitHub provider readiness.

    General resource-scoped viewing remains denied until #724 admission.
    """
    if not local_super_admin(current_user):
        abort(403)


def _uncached_render(template: str, **context) -> ResponseReturnValue:
    response = make_response(render_template(template, **context))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@source_control_bp.get('/')
@permission_required('integrations.manage')
def overview() -> ResponseReturnValue:
    """UAT-only until production installation-scoped authorization is admitted."""
    _require_product_uat_access()
    active_tab = request.args.get('tab', 'overview', type=str)
    if active_tab not in {'overview', 'capacity', 'signals', 'reporting'}:
        active_tab = 'overview'
    authorized_scope = build_source_control_overview()
    raw_installation_id = request.args.get('installation_id', '').strip()
    selected_installation = None
    scope = authorized_scope
    if raw_installation_id:
        if len(raw_installation_id) > 18 or not raw_installation_id.isascii() or not raw_installation_id.isdecimal():
            abort(404)
        installation_id = int(raw_installation_id)
        if installation_id < 1:
            abort(404)
        selected_installation = next(
            (item for item in authorized_scope['installations'] if item['installation'].id == installation_id),
            None,
        )
        if selected_installation is None:
            abort(404)
        scope = {
            **authorized_scope,
            'installations': (selected_installation,),
            'installation_count': 1,
            'committed_count': int(selected_installation['committed']),
            'uncollected_count': int(not selected_installation['committed']),
            'latest_committed_at': selected_installation['last_committed_at'],
            'has_more': False,
        }
    installation_rows, installation_pagination = paginate_sequence(
        scope['installations'],
        page=request.args.get('installation_page'),
        per_page=request.args.get('installation_per_page'),
    )
    repository_coverage = (
        read_repository_coverage_for_current_session(
            authorized_installation_id=selected_installation['installation'].id
        )
        if selected_installation is not None and active_tab == 'capacity'
        else None
    )
    return _uncached_render(
        'source_control/overview.html',
        scope=scope,
        dashboard_active_tab=active_tab,
        authorized_installations=authorized_scope['installations'],
        authorized_scope_has_more=authorized_scope.get('has_more', False),
        selected_installation_id=(selected_installation['installation'].id if selected_installation else None),
        selected_installation_name=(selected_installation['connection'].name if selected_installation else None),
        installation_rows=installation_rows,
        installation_pagination=installation_pagination,
        repository_coverage=repository_coverage,
    )


@source_control_bp.get('/repositories')
@permission_required('integrations.manage')
def repositories() -> ResponseReturnValue:
    """Explicit scope only; never fall back to a tenant-wide repository query."""
    _require_product_uat_access()
    scope = build_source_control_overview()
    raw_installation_id = request.args.get('installation_id', '').strip()
    selected = None
    inventory = None
    search = request.args.get('inventory_search', '').strip()[:80]
    visibility = request.args.get('inventory_visibility', '').strip().lower()
    archived = request.args.get('inventory_archived', '').strip().lower()
    if visibility not in {'public', 'private', 'internal', 'unknown'}:
        visibility = ''
    if archived not in {'active', 'archived', 'unknown'}:
        archived = ''

    if raw_installation_id:
        if len(raw_installation_id) > 18 or not raw_installation_id.isascii() or not raw_installation_id.isdecimal():
            abort(404)
        installation_id = int(raw_installation_id)
        if installation_id < 1:
            abort(404)
        selected = next(
            (item for item in scope['installations'] if item['installation'].id == installation_id),
            None,
        )
        if selected is None:
            abort(404)
        page = max(request.args.get('page', 1, type=int) or 1, 1)
        per_page = request.args.get('per_page', 5, type=int) or 5
        if per_page not in _PAGE_SIZES:
            per_page = 5
        inventory = read_installation_inventory_for_current_session(
            authorized_installation_id=installation_id,
            page=page,
            per_page=per_page,
            search=search,
            visibility=visibility,
            archived=archived,
        )

    context = {
        'scope': scope,
        'selected': selected,
        'installation': selected['installation'] if selected is not None else None,
        'inventory': inventory,
        'inventory_search': search,
        'inventory_visibility': visibility,
        'inventory_archived': archived,
        'inventory_href_endpoint': 'source_control.repositories',
        'inventory_htmx_endpoint': 'source_control.repositories',
    }
    if request.headers.get('HX-Request') == 'true' and selected is not None:
        return _uncached_render('integrations/source_control/github/_inventory_table.html', **context)
    return _uncached_render('source_control/repositories.html', **context)
