from __future__ import annotations

from flask import render_template, request

from app.analytics.forecast.service import get_forecast_analysis_context
from app.analytics.materialization.presentation import pending_page_context, snapshot_meta
from app.analytics.materialization.requests import resolve_materialized_request
from app.common.dependencies import render_dependency_blocker
from app.prometheus.repository import resolve_instance_for_cluster
from app.rbac.decorators import permission_required


def _context_or_pending():
    parameters = request.args.to_dict(flat=True)
    parameters.setdefault('history_window', '30d')
    parameters.setdefault('forecast_horizon', '90d')
    parameters.setdefault('resource', 'all')
    parameters.setdefault('method', 'linear')
    materialized = resolve_materialized_request(
        dataset_key='analytics.forecast',
        job_key='analytics.forecast.materialize',
        parameters=parameters,
    )
    if materialized.cluster is None or resolve_instance_for_cluster(materialized.cluster.id) is None:
        return get_forecast_analysis_context(query_args=request.args), None
    if not materialized.result.available:
        return None, pending_page_context(
            materialized=materialized,
            dataset_key='analytics.forecast',
            title='Capacity Forecast',
            description=(
                'Forecast range queries run on the dedicated forecasting worker '
                'and never block the web request.'
            ),
            icon='chart-spline',
        )
    context = materialized.result.context or {}
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


@permission_required('analytics.view')
def forecast() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/pending.html', **pending)
    return render_template('analytics/forecast/index.html', **(context or {}))


@permission_required('analytics.view')
def forecast_section() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/_pending.html', **pending)
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(dependency_blocker)
    return render_template('analytics/forecast/partials/_forecast_section.html', **(context or {}))
