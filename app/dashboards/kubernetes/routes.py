from __future__ import annotations

from flask import Blueprint, abort, render_template, request

from app.cluster.onboarding import has_registered_clusters
from app.dashboards.kubernetes.service import get_dashboard_overview, get_dashboard_section
from app.rbac.decorators import permission_required

kubernetes_dashboard_bp = Blueprint(
    'kubernetes_dashboard',
    __name__,
    url_prefix='/dashboards/kubernetes',
)

SECTION_TEMPLATES = {
    'kpi_cards': 'dashboards/kubernetes/partials/_kpi_cards.html',
    'cluster_health': 'dashboards/kubernetes/partials/_cluster_health.html',
    'capacity_snapshot': 'dashboards/kubernetes/partials/_capacity_snapshot.html',
    'alerts_summary': 'dashboards/kubernetes/partials/_alerts_summary.html',
    'top_consumers': 'dashboards/kubernetes/partials/_top_consumers.html',
    'forecast_risk': 'dashboards/kubernetes/partials/_forecast_risk.html',
    'data_freshness': 'dashboards/kubernetes/partials/_data_freshness.html',
    'recommended_actions': 'dashboards/kubernetes/partials/_recommended_actions.html',
}


@kubernetes_dashboard_bp.before_request
def block_clusterless_sections():
    """Keep lazy sections aligned with the full-page Kubernetes blocker."""
    if request.endpoint != 'kubernetes_dashboard.section':
        return None
    if has_registered_clusters() is False:
        return render_template('components/cluster/_onboarding_banner.html')
    return None


@kubernetes_dashboard_bp.route('')
@kubernetes_dashboard_bp.route('/')
@permission_required('dashboard.view')
def index():
    selected_cluster_id = request.args.get('cluster_id') or None
    cluster_health_page = request.args.get('cluster_health_page', '1')
    dashboard = get_dashboard_overview(
        selected_cluster_id=selected_cluster_id,
        cluster_health_page=cluster_health_page,
    )
    template_name = (
        'dashboards/kubernetes/partials/_content.html'
        if request.headers.get('HX-Request')
        else 'dashboards/kubernetes/index.html'
    )
    return render_template(template_name, dashboard=dashboard)


@kubernetes_dashboard_bp.route('/section/<string:section>')
@permission_required('dashboard.view')
def section(section: str):
    template_name = SECTION_TEMPLATES.get(section)
    if template_name is None:
        abort(404)

    dashboard = get_dashboard_section(
        section,
        selected_cluster_id=request.args.get('cluster_id') or None,
        cluster_health_page=request.args.get('cluster_health_page', '1'),
    )
    return render_template(template_name, dashboard=dashboard)
