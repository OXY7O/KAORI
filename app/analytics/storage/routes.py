# app/analytics/storage/routes.py

from __future__ import annotations

from flask import render_template, request

from app.analytics.storage.service import get_storage_analysis_context
from app.rbac.decorators import permission_required


@permission_required('analytics.view')
def storage() -> str:
    context = get_storage_analysis_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/storage/index.html',
        **context,
    )


@permission_required('analytics.view')
def storage_filesystem_summary() -> str:
    context = get_storage_analysis_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/storage/partials/_filesystem_panel.html',
        **context,
    )


@permission_required('analytics.view')
def storage_persistent_summary() -> str:
    context = get_storage_analysis_context(
        query_args=request.args,
    )

    return render_template(
        'analytics/storage/partials/_persistent_storage_panel.html',
        **context,
    )
