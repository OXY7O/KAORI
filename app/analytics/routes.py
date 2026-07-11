from flask import Blueprint, redirect, render_template, request, url_for

from app.analytics.alerts.routes import (
    alerts,
    alerts_table,
    anomalies_table,
)
from app.analytics.capacity.routes import capacity
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.forecast.routes import (
    forecast,
    forecast_section,
)
from app.analytics.overview.service import get_analytics_overview, get_analytics_overview_section
from app.analytics.storage.routes import (
    storage,
    storage_filesystem_summary,
    storage_persistent_summary,
)
from app.analytics.top_consumers.routes import (
    top_consumers,
    top_consumers_section,
    top_consumers_table,
)
from app.analytics.utilization.routes import (
    utilization,
    utilization_node_detail,
    utilization_trend,
)
from app.analytics.workload.routes import (
    workload,
    workload_resource_mapping,
    workload_tenant_quota,
)
from app.rbac.decorators import permission_required

analytics_bp = Blueprint(
    'analytics',
    __name__,
    url_prefix='/analytics',
)


VALID_ANALYTICS_TIME_RANGES = {
    '1h',
    '6h',
    '12h',
    '24h',
    '7d',
    '30d',
    '60d',
}


@analytics_bp.route(
    '/',
    methods=[
        'GET',
    ],
)
@permission_required('analytics.view')
def overview():
    selected_cluster_id = request.args.get('cluster_id')
    selected_time_range = request.args.get(
        'time_range',
        '24h',
    )

    if selected_time_range not in VALID_ANALYTICS_TIME_RANGES:
        selected_time_range = '24h'

    payload = get_analytics_overview(
        selected_cluster_id=selected_cluster_id,
        time_range=selected_time_range,
        hydrate_live_sections=False,
    )
    _, _, _, dependency_context = build_analysis_utilization_context(request.args)

    return render_template(
        'analytics/overview/index.html',
        payload=payload,
        dependency_blocker=dependency_context['dependency_blocker'],
    )


@analytics_bp.route(
    '/overview/section/<string:section>',
    methods=[
        'GET',
    ],
)
@permission_required('analytics.view')
def overview_section(section: str):
    allowed_sections = {
        'health-summary': 'analytics/overview/partials/_health_summary.html',
        'hero-posture': 'analytics/overview/partials/_hero_posture.html',
        'prometheus-status': 'analytics/overview/partials/_prometheus_status.html',
        'resource-snapshot': 'analytics/overview/partials/_resource_snapshot.html',
        'capacity-snapshot': 'analytics/overview/partials/_capacity_snapshot.html',
        'actionable-recommendations': 'analytics/overview/partials/_actionable_recommendation_summary.html',
        'storage-snapshot': 'analytics/overview/partials/_storage_snapshot.html',
        'workload-snapshot': 'analytics/overview/partials/_workload_snapshot.html',
        'top-consumers': 'analytics/overview/partials/_top_consumers_snapshot.html',
        'forecast-snapshot': 'analytics/overview/partials/_forecast_snapshot.html',
        'alerts-snapshot': 'analytics/overview/partials/_alerts_snapshot.html',
        'recommendations': 'analytics/overview/partials/_recommendations.html',
    }

    template_name = allowed_sections.get(section)

    if not template_name:
        return '', 404

    selected_time_range = request.args.get(
        'time_range',
        '24h',
    )

    if selected_time_range not in VALID_ANALYTICS_TIME_RANGES:
        selected_time_range = '24h'

    _, _, _, dependency_context = build_analysis_utilization_context(request.args)
    dependency_blocker = dependency_context['dependency_blocker']

    if dependency_blocker:
        return render_template(
            'components/dependencies/_blocker.html',
            dependency_blocker=dependency_blocker,
        )

    payload = get_analytics_overview_section(
        section=section,
        selected_cluster_id=request.args.get('cluster_id'),
        time_range=selected_time_range,
    )

    return render_template(
        template_name,
        payload=payload,
    )


analytics_bp.add_url_rule(
    '/utilization',
    endpoint='utilization',
    view_func=utilization,
)

analytics_bp.add_url_rule(
    '/utilization/node-detail',
    endpoint='utilization_node_detail',
    view_func=utilization_node_detail,
)

analytics_bp.add_url_rule(
    '/utilization/trend',
    endpoint='utilization_trend',
    view_func=utilization_trend,
)

analytics_bp.add_url_rule(
    '/capacity',
    endpoint='capacity',
    view_func=capacity,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/storage',
    endpoint='storage',
    view_func=storage,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/storage/filesystem-summary',
    endpoint='storage_filesystem_summary',
    view_func=storage_filesystem_summary,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/storage/persistent-summary',
    endpoint='storage_persistent_summary',
    view_func=storage_persistent_summary,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/workload',
    endpoint='workload',
    view_func=workload,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/workload/tenant-quota',
    endpoint='workload_tenant_quota',
    view_func=workload_tenant_quota,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/workload/resource-mapping',
    endpoint='workload_resource_mapping',
    view_func=workload_resource_mapping,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/forecast',
    endpoint='forecast',
    view_func=forecast,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/forecast/section',
    endpoint='forecast_section',
    view_func=forecast_section,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/top-consumers',
    endpoint='top_consumers',
    view_func=top_consumers,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/top-consumers/section',
    endpoint='top_consumers_section',
    view_func=top_consumers_section,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/top-consumers/table',
    endpoint='top_consumers_table',
    view_func=top_consumers_table,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/alerts',
    endpoint='alerts',
    view_func=alerts,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/alerts-anomalies',
    endpoint='alerts_anomalies',
    view_func=alerts,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/alerts/table',
    endpoint='alerts_table',
    view_func=alerts_table,
    methods=[
        'GET',
    ],
)

analytics_bp.add_url_rule(
    '/alerts/anomalies',
    endpoint='alerts_anomalies_table',
    view_func=anomalies_table,
    methods=[
        'GET',
    ],
)


@analytics_bp.route('/anomalies')
@permission_required('analytics.view')
def anomalies():
    return redirect(
        url_for(
            'analytics.alerts',
        )
    )
