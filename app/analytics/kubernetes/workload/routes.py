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

from app.analytics.kubernetes.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.analytics.kubernetes.materialization.requests import resolve_materialized_request
from app.analytics.kubernetes.workload.presentation import present_workload_materialized_context
from app.analytics.shared.params import get_selected_time_range
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required

_PAGE = {
    'dataset_key': 'analytics.workload',
    'title': 'Workload Analysis',
    'description': 'Workload analytics are prepared by the analytics worker and reused across viewers from committed quota, runtime, and resource snapshots.',
    'icon': 'boxes',
    'page_id': 'workload-page',
}
_WORKLOAD_TABS = {'quotas', 'mapping', 'recommendations'}


def _snapshot_parameters() -> dict[str, str]:
    """Workload snapshots vary only by cluster and observation window.

    Namespace, tab, search, filters, and pagination are presentation state and
    must never create additional materialization variants.
    """
    parameters: dict[str, str] = {}
    cluster_id = request.args.get('cluster_id', type=str)
    time_range = get_selected_time_range(query_args=request.args)
    if cluster_id:
        parameters['cluster_id'] = cluster_id
    parameters['time_range'] = time_range
    return parameters


def _selected_tab(default: str = 'quotas') -> str:
    selected = request.args.get('tab', default=default, type=str)
    return selected if selected in _WORKLOAD_TABS else default


def _context_or_state():
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters=_snapshot_parameters(),
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = present_workload_materialized_context(
                materialized.result.context or {},
                request.args,
            )
            context['dependency_blocker'] = materialized.dependency_blocker
            context['analytics_materialization'] = snapshot_meta(materialized)
            context['initial_tab'] = _selected_tab()
            return context, None
        return None, blocked_page_context(
            materialized=materialized,
            **{key: value for key, value in _PAGE.items() if key != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_workload_materialized_context(
        materialized.result.context or {},
        request.args,
    )
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['initial_tab'] = _selected_tab()
    return context, None


def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request', '').lower() == 'true'


def _full_workload_url(tab: str) -> str:
    query_args: dict[str, Any] = request.args.to_dict(flat=True)
    query_args['tab'] = tab
    return url_for('analytics.workload', **query_args)


def _partial_response(template: str, context: dict, *, tab: str) -> Response:
    response = make_response(render_template(template, **context))
    response.headers['HX-Push-Url'] = _full_workload_url(tab)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


def _partial_state_response(state: dict, *, tab: str) -> Response:
    blocker = state.get('dependency_blocker')
    if blocker:
        response = make_response(render_dependency_blocker(blocker))
    else:
        response = make_response(render_template('analytics/kubernetes/materialization/_pending.html', **state))
    response.headers['HX-Push-Url'] = _full_workload_url(tab)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


@permission_required('analytics.view')
def workload() -> ResponseReturnValue:
    context, state = _context_or_state()
    if state:
        template = (
            'analytics/kubernetes/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/kubernetes/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/kubernetes/workload/index.html', **(context or {}))


@permission_required('analytics.view')
def workload_tenant_quota() -> ResponseReturnValue:
    if not _is_htmx_request():
        return redirect(_full_workload_url('quotas'))
    context, state = _context_or_state()
    if state:
        return _partial_state_response(state, tab='quotas')
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return _partial_state_response(
            {'dependency_blocker': dependency_blocker},
            tab='quotas',
        )
    return _partial_response(
        'analytics/kubernetes/workload/partials/_tenant_quota_section.html',
        context or {},
        tab='quotas',
    )


@permission_required('analytics.view')
def workload_resource_mapping() -> ResponseReturnValue:
    if not _is_htmx_request():
        return redirect(_full_workload_url('mapping'))
    context, state = _context_or_state()
    if state:
        return _partial_state_response(state, tab='mapping')
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return _partial_state_response(
            {'dependency_blocker': dependency_blocker},
            tab='mapping',
        )
    return _partial_response(
        'analytics/kubernetes/workload/partials/_workload_mapping_section.html',
        context or {},
        tab='mapping',
    )
