from __future__ import annotations

from flask import Response, make_response, render_template, request, url_for

from app.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.analytics.materialization.requests import resolve_materialized_request
from app.analytics.storage.service import (
    get_selected_storage_tab,
    present_storage_materialized_context,
)
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required


_PAGE = {
    'dataset_key': 'analytics.storage',
    'title': 'Storage Analysis',
    'description': 'Storage analytics are prepared by the worker and shared across concurrent viewers.',
    'icon': 'database',
    'page_id': 'storage-page',
}


def _snapshot_parameters() -> dict[str, str]:
    """Storage snapshots are cluster-scoped; UI filters remain presentation state."""
    cluster_id = request.args.get('cluster_id', type=str)
    return {'cluster_id': cluster_id} if cluster_id else {}


def _context_or_state():
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters=_snapshot_parameters(),
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = present_storage_materialized_context(
                materialized.result.context or {},
                request.args,
            )
            context['dependency_blocker'] = materialized.dependency_blocker
            context['analytics_materialization'] = snapshot_meta(materialized)
            context['initial_tab'] = get_selected_storage_tab(request.args)
            return context, None
        return None, blocked_page_context(
            materialized=materialized,
            **{k: v for k, v in _PAGE.items() if k != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_storage_materialized_context(materialized.result.context or {}, request.args)
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['initial_tab'] = get_selected_storage_tab(request.args)
    return context, None


def _full_storage_url(tab: str) -> str:
    query_args = request.args.to_dict(flat=True)
    query_args['tab'] = tab
    return url_for('analytics.storage', **query_args)


def _partial_response(template: str, context: dict, *, tab: str) -> Response:
    response = make_response(render_template(template, **context))
    response.headers['HX-Push-Url'] = _full_storage_url(tab)
    return response


@permission_required('analytics.view')
def storage() -> str:
    context, state = _context_or_state()
    if state:
        template = (
            'analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/storage/index.html', **(context or {}))


@permission_required('analytics.view')
def storage_filesystem_summary() -> str | Response:
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
    return _partial_response(
        'analytics/storage/partials/_filesystem_panel.html',
        context or {},
        tab='filesystem',
    )


@permission_required('analytics.view')
def storage_persistent_summary() -> str | Response:
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
    selected_tab = get_selected_storage_tab(request.args, default='pvc')
    if selected_tab not in {'pvc', 'pv'}:
        selected_tab = 'pvc'
    context = dict(context or {})
    context['selected_storage_tab'] = selected_tab
    return _partial_response(
        'analytics/storage/partials/_persistent_storage_panel.html',
        context,
        tab=selected_tab,
    )
