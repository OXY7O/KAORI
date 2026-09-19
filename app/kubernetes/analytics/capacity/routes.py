from __future__ import annotations

from flask import render_template, request

from app.access.rbac.decorators import permission_required
from app.kubernetes.analytics.capacity.presentation import present_capacity_context
from app.kubernetes.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.kubernetes.analytics.materialization.requests import resolve_materialized_request

_ALLOWED_TABS = {'summary', 'allocation', 'risk', 'recommendations'}


def _initial_tab() -> str:
    requested = request.args.get('tab', 'summary', type=str)
    return requested if requested in _ALLOWED_TABS else 'summary'


_PAGE = {
    'dataset_key': 'analytics.capacity',
    'title': 'Capacity Analysis',
    'description': 'KAORI prepares capacity, allocation, and headroom results before long-range analysis begins.',
    'icon': 'server-cog',
    'page_id': 'capacity-page',
}


@permission_required('analytics.view')
def capacity() -> str:
    parameters = request.args.to_dict(flat=True)
    parameters.pop('tab', None)
    parameters.setdefault('time_range', '24h')
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters=parameters,
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = present_capacity_context(materialized.result.context or {})
            context['dependency_blocker'] = materialized.dependency_blocker
            context['analytics_materialization'] = snapshot_meta(materialized)
            context['initial_tab'] = _initial_tab()
            return render_template('kubernetes/analytics/capacity/index.html', **context)
        return render_template(
            'kubernetes/analytics/materialization/blocked.html',
            **blocked_page_context(
                materialized=materialized,
                **{k: v for k, v in _PAGE.items() if k != 'dataset_key'},
            ),
        )
    if not materialized.result.available:
        return render_template(
            'kubernetes/analytics/materialization/pending.html',
            **pending_page_context(materialized=materialized, **_PAGE),
        )
    context = present_capacity_context(materialized.result.context or {})
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['initial_tab'] = _initial_tab()
    return render_template('kubernetes/analytics/capacity/index.html', **context)
