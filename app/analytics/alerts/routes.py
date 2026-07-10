from __future__ import annotations

from flask import render_template, request
from flask.typing import ResponseReturnValue

from app.analytics.alerts.service import get_alerts_context
from app.rbac.decorators import permission_required


def _context_from_request() -> dict:
    return get_alerts_context(
        cluster_id=request.args.get(
            'cluster_id',
        ),
        source=request.args.get(
            'source',
        ),
        severity=request.args.get(
            'severity',
        ),
        status=request.args.get(
            'status',
        ),
        namespace=request.args.get(
            'namespace',
        ),
        search=request.args.get(
            'search',
        ),
        page=request.args.get(
            'page',
            '1',
        ),
        alerts_per_page=request.args.get(
            'alerts_per_page',
            request.args.get(
                'per_page',
                '5',
            ),
        ),
        anomalies_per_page=request.args.get(
            'anomalies_per_page',
            request.args.get(
                'per_page',
                '5',
            ),
        ),
    )


@permission_required('analytics.view')
def alerts() -> ResponseReturnValue:
    return render_template(
        'analytics/alerts/index.html',
        **_context_from_request(),
    )


@permission_required('analytics.view')
def alerts_table() -> ResponseReturnValue:
    return render_template(
        'analytics/alerts/partials/_alerts_table.html',
        **_context_from_request(),
    )


@permission_required('analytics.view')
def anomalies_table() -> ResponseReturnValue:
    return render_template(
        'analytics/alerts/partials/_anomalies_table.html',
        **_context_from_request(),
    )
