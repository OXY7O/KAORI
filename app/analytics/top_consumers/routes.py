from __future__ import annotations

from flask import render_template, request

from app.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.analytics.materialization.requests import resolve_materialized_request
from app.analytics.top_consumers.service import present_top_consumers_materialized_context
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required


_PAGE = {
    'dataset_key': 'analytics.top_consumers',
    'title': 'Top Consumers',
    'description': 'Consumer rankings are prepared by the worker and filtered locally for each viewer.',
    'icon': 'list-ordered',
    'page_id': 'top-consumers-page',
}


def _context_or_state():
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters=request.args.to_dict(flat=True),
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = present_top_consumers_materialized_context(
                materialized.result.context or {},
                request.args,
            )
            context['dependency_blocker'] = materialized.dependency_blocker
            context['analytics_materialization'] = snapshot_meta(materialized)
            return context, None
        return None, blocked_page_context(materialized=materialized, **{k: v for k, v in _PAGE.items() if k != 'dataset_key'})
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_top_consumers_materialized_context(materialized.result.context or {}, request.args)
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


@permission_required('analytics.view')
def top_consumers() -> str:
    context, state = _context_or_state()
    if state:
        template = (
            'analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/top_consumers/index.html', **(context or {}))


@permission_required('analytics.view')
def top_consumers_section() -> str:
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
    return render_template('analytics/top_consumers/partials/_top_consumers_section.html', **(context or {}))


@permission_required('analytics.view')
def top_consumers_table() -> str:
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
    return render_template('analytics/top_consumers/partials/_consumer_detail_section.html', **(context or {}))
