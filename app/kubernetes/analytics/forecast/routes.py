from __future__ import annotations

from flask import render_template, request

from app.access.rbac.decorators import permission_required
from app.kubernetes.analytics.forecast.presentation import present_forecast_materialized_context
from app.kubernetes.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.kubernetes.analytics.materialization.requests import resolve_materialized_request

_PAGE = {
    'dataset_key': 'analytics.forecast',
    'title': 'Forecast',
    'description': 'Review committed history while workers prepare forecast analysis.',
    'icon': 'chart-spline',
    'page_id': 'forecast-page',
}


def _snapshot_parameters() -> dict[str, str]:
    """Keep only provider-query dimensions in the forecast snapshot identity."""
    parameters: dict[str, str] = {
        'history_window': request.args.get('history_window', '30d', type=str),
    }
    cluster_id = request.args.get('cluster_id', type=str)
    namespace = request.args.get('namespace', type=str)
    if cluster_id:
        parameters['cluster_id'] = cluster_id
    if namespace:
        parameters['namespace'] = namespace
    return parameters


def _context_or_state():
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.forecast.materialize',
        parameters=_snapshot_parameters(),
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = present_forecast_materialized_context(
                materialized.result.context or {},
                request.args,
            )
            context['dependency_blocker'] = materialized.dependency_blocker
            context['analytics_materialization'] = snapshot_meta(materialized)
            return context, None
        return None, blocked_page_context(
            materialized=materialized,
            **{key: value for key, value in _PAGE.items() if key != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_forecast_materialized_context(
        materialized.result.context or {},
        request.args,
    )
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


@permission_required('analytics.view')
def forecast() -> str:
    context, state = _context_or_state()
    if state:
        template = (
            'kubernetes/analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'kubernetes/analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('kubernetes/analytics/forecast/index.html', **(context or {}))
