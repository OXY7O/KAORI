# app/analytics/top_consumers/routes.py

from __future__ import annotations

from flask import render_template, request

from app.analytics.top_consumers.service import get_top_consumers_context
from app.rbac.decorators import permission_required


@permission_required('analytics.view')
def top_consumers() -> str:
    context = get_top_consumers_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/top_consumers/index.html',
        **context,
    )


@permission_required('analytics.view')
def top_consumers_section() -> str:
    context = get_top_consumers_context(
        query_args=request.args,
    )

    context['render_dependency_blocker'] = True

    return render_template(
        'analytics/top_consumers/partials/_top_consumers_section.html',
        **context,
    )


@permission_required('analytics.view')
def top_consumers_table() -> str:
    context = get_top_consumers_context(
        query_args=request.args,
    )

    context['render_dependency_blocker'] = True

    return render_template(
        'analytics/top_consumers/partials/_consumer_detail_section.html',
        **context,
    )
