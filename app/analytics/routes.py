from hashlib import sha256

from flask import (
    Blueprint,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user

from app.analytics.alerts.routes import alerts, alerts_table, anomalies_table
from app.analytics.capacity.routes import capacity
from app.analytics.forecast.routes import forecast
from app.analytics.materialization.presentation import materialization_progress_context
from app.analytics.object_storage.routes import (
    object_storage_alerts,
    object_storage_capacity,
    object_storage_forecast,
    object_storage_overview,
    object_storage_performance,
    object_storage_top_consumers,
)
from app.analytics.overview.sections import get_overview_section
from app.analytics.overview.service import get_analytics_overview, get_analytics_overview_section
from app.analytics.storage.routes import storage, storage_filesystem_summary, storage_persistent_summary
from app.analytics.top_consumers.routes import top_consumers, top_consumers_table
from app.analytics.utilization.routes import utilization, utilization_node_detail, utilization_trend
from app.analytics.workload.routes import workload, workload_resource_mapping, workload_tenant_quota
from app.common.dependencies import cluster_required_blocker
from app.common.integration_errors import describe_integration_failure
from app.notifications.service import get_navigation_notification_context, record_operational_activity
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


PROMETHEUS_FAILURE_SESSION_KEY = 'analytics_overview_prometheus_failures'
PROMETHEUS_FAILURE_SESSION_LIMIT = 32


def _render_operational_toast(feedback: dict) -> str:
    return render_template(
        'components/operational_toast.html',
        **feedback,
        toast_oob=True,
        notification_context=get_navigation_notification_context(
            user_id=current_user.id,
        ),
    )


def _update_prometheus_failure_state(
    *,
    cluster_id: str,
    fingerprint: str | None,
) -> bool:
    state = dict(
        session.get(
            PROMETHEUS_FAILURE_SESSION_KEY,
            {},
        )
    )

    if fingerprint is None:
        if cluster_id in state:
            state.pop(cluster_id, None)
            session[PROMETHEUS_FAILURE_SESSION_KEY] = state
            session.modified = True
        return False

    if state.get(cluster_id) == fingerprint:
        return False

    state[cluster_id] = fingerprint
    if len(state) > PROMETHEUS_FAILURE_SESSION_LIMIT:
        oldest_cluster_id = next(iter(state))
        state.pop(oldest_cluster_id, None)

    session[PROMETHEUS_FAILURE_SESSION_KEY] = state
    session.modified = True
    return True


def _build_prometheus_failure_feedback(payload: dict) -> str:
    prometheus = payload.get('prometheus') or {}
    selected_cluster = payload.get('selected_cluster') or {}
    cluster_id = str(selected_cluster.get('id') or payload.get('selected_cluster_id') or '')

    if not cluster_id:
        return ''

    if prometheus.get('connected') or not prometheus.get('configured'):
        _update_prometheus_failure_state(
            cluster_id=cluster_id,
            fingerprint=None,
        )
        return ''

    endpoint = str(prometheus.get('endpoint') or '').strip()
    diagnostic_detail = str(
        prometheus.get('diagnostic_detail') or 'The Prometheus health check did not complete successfully.'
    ).strip()
    fingerprint = sha256(
        f'{endpoint}|{diagnostic_detail}'.encode(),
    ).hexdigest()

    if not _update_prometheus_failure_state(
        cluster_id=cluster_id,
        fingerprint=fingerprint,
    ):
        return ''

    failure = describe_integration_failure(
        RuntimeError(diagnostic_detail),
        service_name='Prometheus',
        endpoint=endpoint,
        request_path='/api/v1/query',
    )
    cluster_name = str(selected_cluster.get('name') or 'Selected cluster')
    environment = str(selected_cluster.get('environment') or '')

    feedback = record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_health_check_failed',
        status='error',
        title='Prometheus connection failed',
        message=f'Prometheus is unreachable for {cluster_name}.',
        detail=str(failure['detail']),
        metadata={
            'cluster_id': cluster_id,
            'cluster_name': cluster_name,
            'environment': environment,
            'endpoint': endpoint,
            'failure_code': failure['code'],
            'reason': failure['reason'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        },
    )

    return _render_operational_toast(feedback)


@analytics_bp.get('/materialization/status')
@permission_required('analytics.view')
def materialization_status():
    from app.analytics.materialization.service import read_snapshot

    dataset_key = request.args.get('dataset_key', '').strip()
    cluster_id = request.args.get('cluster_id', '').strip()
    if not dataset_key or not cluster_id:
        return '', 400

    from app.analytics.materialization.catalog import canonical_parameters

    try:
        parameters = canonical_parameters(
            dataset_key,
            {
                key: value
                for key, value in request.args.items()
                if key not in {'dataset_key', 'return_url'} and value != ''
            },
        )
    except LookupError:
        return '', 404
    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
    )
    if result.available:
        response = make_response('', 204)
        response.headers['HX-Refresh'] = 'true'
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response
    progress = materialization_progress_context(result.snapshot)
    response = make_response(
        render_template(
            'analytics/materialization/_pending.html',
            materialization_status_url=request.full_path,
            materialization_return_url=(request.args.get('return_url', '').strip() or url_for('analytics.overview')),
            **progress,
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


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
        hydrate_snapshot_sections=False,
    )
    return render_template(
        'analytics/overview/index.html',
        payload=payload,
        dependency_blocker=(cluster_required_blocker() if payload.get('selected_cluster') is None else None),
    )


@analytics_bp.route(
    '/overview/section/<string:section>',
    methods=[
        'GET',
    ],
)
@permission_required('analytics.view')
def overview_section(section: str):
    section_definition = get_overview_section(section)
    if section_definition is None:
        return '', 404

    selected_time_range = request.args.get(
        'time_range',
        '24h',
    )

    if selected_time_range not in VALID_ANALYTICS_TIME_RANGES:
        selected_time_range = '24h'

    if request.headers.get('HX-Request') != 'true':
        return redirect(
            url_for(
                'analytics.overview',
                cluster_id=request.args.get('cluster_id'),
                time_range=selected_time_range,
            )
        )

    payload = get_analytics_overview_section(
        section=section,
        selected_cluster_id=request.args.get('cluster_id'),
        time_range=selected_time_range,
    )

    section_html = render_template(
        section_definition.template,
        payload=payload,
    )

    if section == 'health-summary':
        section_html = ''.join(
            (
                section_html,
                render_template(
                    'analytics/overview/partials/_hero_posture_oob.html',
                    payload=payload,
                ),
                render_template(
                    'analytics/overview/partials/_composite_tabs_oob.html',
                    payload=payload,
                ),
                _build_prometheus_failure_feedback(payload),
            )
        )

    response = make_response(section_html)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


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
    '/top-consumers',
    endpoint='top_consumers',
    view_func=top_consumers,
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

analytics_bp.add_url_rule(
    '/object-storage',
    endpoint='object_storage_overview',
    view_func=object_storage_overview,
    methods=['GET'],
)

analytics_bp.add_url_rule(
    '/object-storage/capacity',
    endpoint='object_storage_capacity',
    view_func=object_storage_capacity,
    methods=['GET'],
)

analytics_bp.add_url_rule(
    '/object-storage/performance',
    endpoint='object_storage_performance',
    view_func=object_storage_performance,
    methods=['GET'],
)

analytics_bp.add_url_rule(
    '/object-storage/forecast',
    endpoint='object_storage_forecast',
    view_func=object_storage_forecast,
    methods=['GET'],
)

analytics_bp.add_url_rule(
    '/object-storage/top-consumers',
    endpoint='object_storage_top_consumers',
    view_func=object_storage_top_consumers,
    methods=['GET'],
)

analytics_bp.add_url_rule(
    '/object-storage/alerts',
    endpoint='object_storage_alerts',
    view_func=object_storage_alerts,
    methods=['GET'],
)
