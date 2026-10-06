from __future__ import annotations

from flask import (
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue

from app.access.rbac.decorators import permission_required
from app.kubernetes.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.kubernetes.analytics.materialization.requests import resolve_materialized_request
from app.kubernetes.analytics.utilization.materialization import ALLOWED_TREND_HOURS, build_utilization_trend_summary
from app.kubernetes.analytics.utilization.presentation import (
    build_node_presentation,
    build_summary_presentation,
    build_trend_options,
    build_trend_presentation,
)
from app.kubernetes.analytics.utilization.service import get_utilization_clusters

_PAGE = {
    'dataset_key': 'analytics.utilization.summary',
    'title': 'Utilization',
    'description': 'Review utilization while workers prepare current analytics evidence.',
    'icon': 'chart-no-axes-combined',
    'page_id': 'utilization-page',
}


def _trend_hours() -> int:
    try:
        value = int(request.args.get('trend_hours', '24'))
    except (TypeError, ValueError):
        return 24
    return value if value in ALLOWED_TREND_HOURS else 24


def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request') == 'true'


def _fragment_response(template: str, **context) -> ResponseReturnValue:
    response = make_response(render_template(template, **context))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


def _redirect_to_workspace(*, tab: str) -> ResponseReturnValue:
    return redirect(
        url_for(
            'analytics.utilization',
            cluster_id=request.args.get('cluster_id', ''),
            trend_hours=_trend_hours(),
            trend_node=request.args.get('trend_node', ''),
            node=request.args.get('node', ''),
            tab=tab,
        )
    )


def _decorate_summary_context(
    context,
    materialized,
    *,
    trend_hours,
    selected_node,
    selected_trend_node,
):
    context.update(
        {
            'clusters': get_utilization_clusters(),
            'cluster': materialized.cluster,
            'trend_hours': trend_hours,
            'trend_options': build_trend_options(ALLOWED_TREND_HOURS, trend_hours),
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
    context['utilization_presentation'] = build_summary_presentation(
        summary=context.get('summary'),
        cluster_info=context.get('cluster_info'),
        trend_hours=trend_hours,
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
    # Trend and node datasets are intentionally not resolved here. Their tabs own
    # first activation, materialization dispatch, polling, and rendering.
    return context, None


@permission_required('analytics.view')
def utilization() -> ResponseReturnValue:
    context, state = _base_context_or_state()
    if state:
        template = (
            'kubernetes/analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'kubernetes/analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('kubernetes/analytics/utilization/index.html', **(context or {}))


@permission_required('analytics.view')
def utilization_trend() -> ResponseReturnValue:
    if not _is_htmx_request():
        return _redirect_to_workspace(tab='trend')

    trend_hours = _trend_hours()
    selected_trend_node = request.args.get('trend_node', '')
    materialized = resolve_materialized_request(
        dataset_key='analytics.utilization.trend',
        job_key='analytics.materialize',
        parameters={
            'cluster_id': request.args.get('cluster_id', ''),
            'trend_hours': str(trend_hours),
            'trend_node': selected_trend_node,
        },
    )
    if materialized.dependency_blocker:
        return _fragment_response(
            'components/dependencies/_blocker.html',
            dependency_blocker=materialized.dependency_blocker,
        )
    if not materialized.result.available:
        return _fragment_response(
            'kubernetes/analytics/utilization/partials/_trend_pending.html',
            cluster_id=request.args.get('cluster_id', ''),
            trend_hours=trend_hours,
            selected_trend_node=selected_trend_node,
        )
    context = dict(materialized.result.context or {})
    context.setdefault('trends', {'cpu': [], 'memory': [], 'pods': []})
    context.setdefault('trend_summary', build_utilization_trend_summary(context['trends']))
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['trend_presentation'] = build_trend_presentation(
        trend_summary=context.get('trend_summary'),
        trend_hours=trend_hours,
        selected_node=str(context.get('selected_trend_node') or selected_trend_node),
    )
    return _fragment_response('kubernetes/analytics/utilization/partials/_trend.html', **context)


@permission_required('analytics.view')
def utilization_node_detail() -> ResponseReturnValue:
    if not _is_htmx_request():
        return _redirect_to_workspace(tab='nodes')

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
        return _fragment_response(
            'components/dependencies/_blocker.html',
            dependency_blocker=materialized.dependency_blocker,
        )
    if not materialized.result.available:
        return _fragment_response(
            'kubernetes/analytics/utilization/partials/_node_pending.html',
            cluster_id=request.args.get('cluster_id', ''),
            selected_node=selected_node,
        )
    context = dict(materialized.result.context or {})
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['node_presentation'] = build_node_presentation(
        detail_summary=context.get('detail_summary'),
        risk_assessment=context.get('detail_risk_assessment'),
        selected_node=str(context.get('selected_node') or selected_node),
    )
    return _fragment_response('kubernetes/analytics/utilization/partials/_node_detail.html', **context)
