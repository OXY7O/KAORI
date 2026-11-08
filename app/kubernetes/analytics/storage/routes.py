from __future__ import annotations

from typing import Any

from flask import (
    Response,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue

from app.access.rbac.decorators import permission_required
from app.common.dependencies import render_dependency_blocker
from app.kubernetes.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.kubernetes.analytics.materialization.requests import resolve_materialized_request
from app.kubernetes.analytics.storage.presentation import get_selected_storage_tab, present_storage_materialized_context

_PAGE = {
    'dataset_key': 'analytics.storage',
    'title': 'Storage',
    'description': 'Review storage snapshots while KAORI prepares analytics evidence.',
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
            **{key: value for key, value in _PAGE.items() if key != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_storage_materialized_context(
        materialized.result.context or {},
        request.args,
    )
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['initial_tab'] = get_selected_storage_tab(request.args)
    return context, None


def _full_storage_url(tab: str) -> str:
    query_args: dict[str, Any] = request.args.to_dict(flat=True)
    query_args['tab'] = tab
    return url_for('analytics.storage', **query_args)


def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request', '').lower() == 'true'


def _partial_response(template: str, context: dict, *, tab: str) -> Response:
    response = make_response(render_template(template, **context))
    response.headers['HX-Push-Url'] = _full_storage_url(tab)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


def _partial_state_response(state: dict, *, tab: str) -> ResponseReturnValue:
    blocker = state.get('dependency_blocker')
    if blocker:
        response = make_response(render_dependency_blocker(blocker))
    else:
        response = make_response(render_template('kubernetes/analytics/materialization/_pending.html', **state))
    response.headers['HX-Push-Url'] = _full_storage_url(tab)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


@permission_required('analytics.view')
def storage() -> ResponseReturnValue:
    context, state = _context_or_state()
    if state:
        template = (
            'kubernetes/analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'kubernetes/analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('kubernetes/analytics/storage/index.html', **(context or {}))


@permission_required('analytics.view')
def storage_filesystem_summary() -> ResponseReturnValue:
    if not _is_htmx_request():
        return redirect(_full_storage_url('filesystem'))
    context, state = _context_or_state()
    if state:
        return _partial_state_response(state, tab='filesystem')
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return _partial_state_response(
            {'dependency_blocker': dependency_blocker},
            tab='filesystem',
        )
    return _partial_response(
        'kubernetes/analytics/storage/partials/_filesystem_panel.html',
        context or {},
        tab='filesystem',
    )


@permission_required('analytics.view')
def storage_persistent_summary() -> ResponseReturnValue:
    selected_tab = get_selected_storage_tab(request.args, default='pvc')
    if selected_tab not in {'pvc', 'pv'}:
        selected_tab = 'pvc'
    if not _is_htmx_request():
        return redirect(_full_storage_url(selected_tab))
    context, state = _context_or_state()
    if state:
        return _partial_state_response(state, tab=selected_tab)
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return _partial_state_response(
            {'dependency_blocker': dependency_blocker},
            tab=selected_tab,
        )
    resolved = dict(context or {})
    resolved['selected_storage_tab'] = selected_tab
    return _partial_response(
        'kubernetes/analytics/storage/partials/_persistent_storage_panel.html',
        resolved,
        tab=selected_tab,
    )
