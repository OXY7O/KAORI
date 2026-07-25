from __future__ import annotations

from flask import render_template, request

from app.analytics.forecast.service import present_forecast_materialized_context
from app.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.analytics.materialization.requests import resolve_materialized_request
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required


_PAGE = {
    'dataset_key': 'analytics.forecast',
    'title': 'Capacity Forecast',
    'description': (
        'Historical range data is prepared by the forecasting worker. '
        'Forecast horizon, method, and resource selectors are projected locally.'
    ),
    'icon': 'chart-spline',
    'page_id': 'forecast-page',
}


def _context_or_state():
    requested = request.args.to_dict(flat=True)
    requested.setdefault('history_window', '30d')
    requested.setdefault('forecast_horizon', '90d')
    requested.setdefault('resource', 'all')
    requested.setdefault('method', 'linear')
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.forecast.materialize',
        parameters=requested,
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
        return None, blocked_page_context(materialized=materialized, **{k: v for k, v in _PAGE.items() if k != 'dataset_key'})
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_forecast_materialized_context(materialized.result.context or {}, request.args)
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


@permission_required('analytics.view')
def forecast() -> str:
    context, state = _context_or_state()
    if state:
        template = (
            'analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/forecast/index.html', **(context or {}))


@permission_required('analytics.view')
def forecast_section() -> str:
    context, state = _context_or_state()
    if state:
        blocker = state.get('dependency_blocker')
        return (
            render_dependency_blocker(blocker)
            if blocker
            else render_template('analytics/materialization/_pending.html', **state)
        )
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(dependency_blocker)
    return render_template('analytics/forecast/partials/_forecast_section.html', **(context or {}))
