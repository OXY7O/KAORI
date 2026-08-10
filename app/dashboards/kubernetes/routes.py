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

DASHBOARD_TABS = {'overview', 'capacity', 'signals', 'reporting'}
CLUSTER_HEALTH_PAGE_SIZES = {5, 10, 25, 50}


def _active_tab() -> str:
    value = str(request.args.get('tab') or 'overview').strip().lower()
    return value if value in DASHBOARD_TABS else 'overview'


def _cluster_health_per_page() -> int:
    try:
        value = int(request.args.get('cluster_health_per_page', '5'))
    except (TypeError, ValueError):
        return 5
    return value if value in CLUSTER_HEALTH_PAGE_SIZES else 5


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


@kubernetes_dashboard_bp.route('')
@kubernetes_dashboard_bp.route('/')
@permission_required('dashboard.view')
def index():
    selected_cluster_id = request.args.get('cluster_id') or None
    cluster_health_page = request.args.get('cluster_health_page', '1')
    dashboard = get_dashboard_overview(
        selected_cluster_id=selected_cluster_id,
        cluster_health_page=cluster_health_page,
        cluster_health_per_page=_cluster_health_per_page(),
        active_tab=_active_tab(),
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

    # This blocker must execute inside the permission-protected view. A
    # blueprint ``before_request`` can short-circuit Flask before the view
    # decorator runs and must never own authorization-sensitive responses.
    if has_registered_clusters() is False:
        return render_template('components/cluster/_onboarding_banner.html')

    dashboard = get_dashboard_section(
        section,
        selected_cluster_id=request.args.get('cluster_id') or None,
        cluster_health_page=request.args.get('cluster_health_page', '1'),
        cluster_health_per_page=_cluster_health_per_page(),
    )
    return render_template(template_name, dashboard=dashboard)
