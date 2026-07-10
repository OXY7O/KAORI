# app/analytics/forecast/routes.py

from __future__ import annotations

from flask import render_template, request
from app.rbac.decorators import permission_required

from app.analytics.forecast.service import get_forecast_analysis_context


@permission_required('analytics.view')
def forecast() -> str:
    context = get_forecast_analysis_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/forecast/index.html',
        **context,
    )


@permission_required('analytics.view')
def forecast_section() -> str:
    context = get_forecast_analysis_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/forecast/partials/_forecast_section.html',
        **context,
    )
