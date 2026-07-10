# app/analytics/capacity/routes.py

from __future__ import annotations

from flask import render_template, request
from app.rbac.decorators import permission_required

from app.analytics.capacity.service import get_capacity_page_context


@permission_required('analytics.view')
def capacity() -> str:
    context = get_capacity_page_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/capacity/index.html',
        **context,
    )
