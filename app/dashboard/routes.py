from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask_login import login_required

from app.dashboard.service import get_dashboard_overview
from app.rbac.decorators import permission_required

dashboard_bp = Blueprint('dashboard', __name__)

_DASHBOARD_SECTION_TEMPLATES = {
    'kpi_cards': 'dashboard/partials/_kpi_cards.html',
    'cluster_health': 'dashboard/partials/_cluster_health.html',
    'capacity_snapshot': 'dashboard/partials/_capacity_snapshot.html',
    'alerts_summary': 'dashboard/partials/_alerts_summary.html',
    'top_consumers': 'dashboard/partials/_top_consumers.html',
    'forecast_risk': 'dashboard/partials/_forecast_risk.html',
    'data_freshness': 'dashboard/partials/_data_freshness.html',
    'recommended_actions': 'dashboard/partials/_recommended_actions.html',
}

_DASHBOARD_SECTION_LIVE_MAP = {
    'kpi_cards': {'kpi_cards'},
    'cluster_health': {'cluster_health'},
    'capacity_snapshot': {'capacity_snapshot'},
    'alerts_summary': {'alerts_summary'},
    'top_consumers': {'top_consumers'},
    'forecast_risk': {'forecast_risk'},
    'data_freshness': {'data_freshness'},
    'recommended_actions': {'recommended_actions'},
}


@dashboard_bp.route('/welcome')
@login_required
def welcome():
    return render_template('dashboard/welcome.html')


@dashboard_bp.route('/')
@permission_required('dashboard.view')
def index():
    selected_cluster_id = request.args.get('cluster_id') or None
    cluster_health_page = request.args.get('cluster_health_page', '1')

    dashboard = get_dashboard_overview(
        selected_cluster_id=selected_cluster_id,
        cluster_health_page=cluster_health_page,
        hydrate_live_sections=False,
    )

    template_name = 'dashboard/partials/_content.html' if request.headers.get('HX-Request') else 'dashboard/index.html'

    return render_template(
        template_name,
        dashboard=dashboard,
    )


@dashboard_bp.route('/dashboard/section/<string:section>')
@permission_required('dashboard.view')
def section(section: str):
    template_name = _DASHBOARD_SECTION_TEMPLATES.get(section)
    if template_name is None:
        abort(404)

    selected_cluster_id = request.args.get('cluster_id') or None
    cluster_health_page = request.args.get('cluster_health_page', '1')

    dashboard = get_dashboard_overview(
        selected_cluster_id=selected_cluster_id,
        cluster_health_page=cluster_health_page,
        hydrate_live_sections=True,
        live_sections=_DASHBOARD_SECTION_LIVE_MAP.get(section, {section}),
    )

    return render_template(
        template_name,
        dashboard=dashboard,
    )
