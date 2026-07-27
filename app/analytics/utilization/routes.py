from __future__ import annotations

from flask import render_template, request

from app.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.analytics.materialization.requests import resolve_materialized_request
from app.analytics.utilization.materialization import (
    ALLOWED_TREND_HOURS,
    build_utilization_trend_summary,
)
from app.analytics.utilization.service import get_utilization_clusters
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required


_PAGE = {
    'dataset_key': 'analytics.utilization.summary',
    'title': 'Resource Utilization',
    'description': 'Utilization summaries are prepared by the analytics worker and served from committed snapshots.',
    'icon': 'chart-no-axes-combined',
    'page_id': 'utilization-page',
}


def _trend_hours() -> int:
    try:
        value = int(request.args.get('trend_hours', '24'))
    except (TypeError, ValueError):
        return 24
    return value if value in ALLOWED_TREND_HOURS else 24


def _decorate_summary_context(context, materialized, *, trend_hours, selected_node, selected_trend_node):
    context.update(
        {
            'clusters': get_utilization_clusters(),
            'cluster': materialized.cluster,
            'trend_hours': trend_hours,
            'allowed_trend_hours': list(ALLOWED_TREND_HOURS),
            'selected_node': selected_node,
            'selected_trend_node': selected_trend_node,
            'cluster_query_endpoint': 'analytics.utilization',
            'cluster_query_hidden_params': {
                'trend_hours': trend_hours,
                'trend_node': selected_trend_node,
                'node': selected_node,
            },
            'analytics_materialization': snapshot_meta(materialized),
        }
    )
    return context


def _base_context_or_state():
    trend_hours = _trend_hours()
    selected_node = request.args.get('node', '', type=str)
    selected_trend_node = request.args.get('trend_node', '', type=str)
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters={'cluster_id': request.args.get('cluster_id', '')},
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = _decorate_summary_context(
                dict(materialized.result.context or {}),
                materialized,
                trend_hours=trend_hours,
                selected_node=selected_node,
                selected_trend_node=selected_trend_node,
            )
            context['dependency_blocker'] = materialized.dependency_blocker
            context['trend_materialization_pending'] = False
            return context, None
        return None, blocked_page_context(
            materialized=materialized,
            **{k: v for k, v in _PAGE.items() if k != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)

    context = _decorate_summary_context(
        dict(materialized.result.context or {}),
        materialized,
        trend_hours=trend_hours,
        selected_node=selected_node,
        selected_trend_node=selected_trend_node,
    )
    trend = resolve_materialized_request(
        dataset_key='analytics.utilization.trend',
        job_key='analytics.materialize',
        parameters={
            'cluster_id': str(materialized.cluster.id),
            'trend_hours': str(trend_hours),
            'trend_node': selected_trend_node,
        },
    )
    trend_context = trend.result.context or {}
    if (
        trend.dependency_blocker is None
        and trend.result.available
        and not trend_context.get('dependency_blocker')
    ):
        context['trends'] = trend_context.get('trends') or {'cpu': [], 'memory': [], 'pods': []}
        context['trend_summary'] = trend_context.get('trend_summary') or build_utilization_trend_summary(
            context['trends']
        )
        context['selected_trend_node'] = trend_context.get('selected_trend_node', selected_trend_node)
        context['available_worker_nodes'] = trend_context.get(
            'available_worker_nodes',
            context.get('available_worker_nodes', []),
        )
        context['trend_materialization_pending'] = False
        context['trend_analytics_materialization'] = snapshot_meta(trend)
    else:
        context.setdefault('trends', {'cpu': [], 'memory': [], 'pods': []})
        context['trend_materialization_pending'] = True
    return context, None


@permission_required('analytics.view')
def utilization() -> str:
    context, state = _base_context_or_state()
    if state:
        template = (
            'analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/utilization/index.html', **(context or {}))


@permission_required('analytics.view')
def utilization_trend() -> str:
    trend_hours = _trend_hours()
    materialized = resolve_materialized_request(
        dataset_key='analytics.utilization.trend',
        job_key='analytics.materialize',
        parameters={
            'cluster_id': request.args.get('cluster_id', ''),
            'trend_hours': str(trend_hours),
            'trend_node': request.args.get('trend_node', ''),
        },
    )
    if materialized.dependency_blocker:
        return render_dependency_blocker(materialized.dependency_blocker)
    if not materialized.result.available:
        pending = pending_page_context(
            materialized=materialized,
            dataset_key='analytics.utilization.trend',
            title='Utilization Trend',
            description='Utilization range queries run on the analytics worker.',
            icon='chart-no-axes-combined',
        )
        return render_template('analytics/materialization/_pending.html', **pending)
    context = dict(materialized.result.context or {})
    context.setdefault('trends', {'cpu': [], 'memory': [], 'pods': []})
    context.setdefault('trend_summary', build_utilization_trend_summary(context['trends']))
    context['analytics_materialization'] = snapshot_meta(materialized)
    return render_template('analytics/utilization/partials/_trend.html', **context)


@permission_required('analytics.view')
def utilization_node_detail() -> str:
    selected_node = request.args.get('node', '', type=str)
    materialized = resolve_materialized_request(
        dataset_key='analytics.utilization.node',
        job_key='analytics.materialize',
        parameters={
            'cluster_id': request.args.get('cluster_id', ''),
            'node': selected_node,
        },
    )
    if materialized.dependency_blocker:
        return render_dependency_blocker(materialized.dependency_blocker)
    if not materialized.result.available:
        pending = pending_page_context(
            materialized=materialized,
            dataset_key='analytics.utilization.node',
            title='Node Utilization',
            description='Node-specific utilization is prepared once and reused while fresh.',
            icon='server',
        )
        return render_template('analytics/materialization/_pending.html', **pending)
    context = dict(materialized.result.context or {})
    context['analytics_materialization'] = snapshot_meta(materialized)
    return render_template('analytics/utilization/partials/_node_detail.html', **context)
