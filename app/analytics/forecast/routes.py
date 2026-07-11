# app/analytics/forecast/routes.py

from __future__ import annotations

from flask import render_template, request

from app.analytics.forecast.service import get_forecast_analysis_context
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required


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

    dependency_blocker = context.get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(
            dependency_blocker,
        )

    return render_template(
        'analytics/forecast/partials/_forecast_section.html',
        **context,
    )
