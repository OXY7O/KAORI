from __future__ import annotations

from flask import Blueprint, abort, render_template, request

from app.access.rbac.decorators import permission_required
from app.dashboards.common.operational import (
    is_htmx_request,
    normalize_dashboard_page_size,
    normalize_operational_tab,
)
from app.storage.object_storage.dashboard.service import get_dashboard_overview, get_dashboard_section

object_storage_dashboard_bp = Blueprint(
    'object_storage_dashboard',
    __name__,
    url_prefix='/dashboards/object-storage',
)

SECTION_TEMPLATES = {
    'kpi_cards': 'storage/object_storage/dashboard/partials/_kpi_cards.html',
    'overview': 'storage/object_storage/dashboard/partials/_overview.html',
    'system_health': 'storage/object_storage/dashboard/partials/_system_health.html',
    'capacity': 'storage/object_storage/dashboard/partials/_capacity.html',
    'signals': 'storage/object_storage/dashboard/partials/_signals.html',
    'reporting': 'storage/object_storage/dashboard/partials/_reporting.html',
}


@object_storage_dashboard_bp.get('/')
@object_storage_dashboard_bp.get('')
@permission_required('dashboard.view')
def index():
    dashboard = get_dashboard_overview(
        selected_system_id=request.args.get('system_id') or None,
        system_health_page=request.args.get('system_health_page', '1'),
        system_health_per_page=normalize_dashboard_page_size(request.args.get('system_health_per_page')),
        active_tab=normalize_operational_tab(request.args.get('tab')),
    )
    template = (
        'storage/object_storage/dashboard/partials/_content.html'
        if is_htmx_request(request.headers)
        else 'storage/object_storage/dashboard/index.html'
    )
    return render_template(template, dashboard=dashboard)


@object_storage_dashboard_bp.get('/section/<string:section>')
@permission_required('dashboard.view')
def section(section: str):
    template = SECTION_TEMPLATES.get(section)
    if template is None:
        abort(404)
    dashboard = get_dashboard_section(
        section,
        selected_system_id=request.args.get('system_id') or None,
        system_health_page=request.args.get('system_health_page', '1'),
        system_health_per_page=_system_health_per_page(),
    )
    return render_template(template, dashboard=dashboard)
