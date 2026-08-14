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

from app.analytics.kubernetes.materialization.presentation import blocked_page_context, pending_page_context, snapshot_meta
from app.analytics.kubernetes.materialization.requests import resolve_materialized_request
from app.analytics.kubernetes.top_consumers.presentation import present_materialized_context
from app.rbac.decorators import permission_required

_PAGE = {
    'dataset_key': 'analytics.top_consumers',
    'title': 'Top Consumers',
    'description': (
        'Consumer rankings use committed cluster or namespace snapshots; record filters remain presentation-only.'
    ),
    'icon': 'list-ordered',
    'page_id': 'top-consumers-page',
}


def _snapshot_parameters() -> dict[str, str]:
    """Top Consumers snapshots vary only by cluster and Namespace."""
    parameters: dict[str, str] = {}
    cluster_id = request.args.get('cluster_id', type=str)
    namespace = request.args.get('namespace', type=str)
    if cluster_id:
        parameters['cluster_id'] = cluster_id
    if namespace:
        parameters['namespace'] = namespace
    return parameters


def _context_or_state():
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters=_snapshot_parameters(),
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = present_materialized_context(
                materialized.result.context or {},
                request.args,
            )
            context['dependency_blocker'] = materialized.dependency_blocker
            context['analytics_materialization'] = snapshot_meta(materialized)
            return context, None
        return None, blocked_page_context(
            materialized=materialized,
            **{key: value for key, value in _PAGE.items() if key != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    context = present_materialized_context(
        materialized.result.context or {},
        request.args,
    )
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request', '').lower() == 'true'


def _full_page_url() -> str:
    query_args: dict[str, Any] = request.args.to_dict(flat=True)
    query_args['tab'] = 'records'
    return url_for('analytics.top_consumers', **query_args)


def _table_response(template: str, context: dict[str, object]) -> Response:
    response = make_response(render_template(template, **context))
    response.headers['HX-Push-Url'] = _full_page_url()
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


@permission_required('analytics.view')
def top_consumers() -> ResponseReturnValue:
    context, state = _context_or_state()
    if state:
        template = (
            'analytics/kubernetes/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/kubernetes/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/kubernetes/top_consumers/index.html', **(context or {}))


@permission_required('analytics.view')
def top_consumers_table() -> ResponseReturnValue:
    if not _is_htmx_request():
        return redirect(_full_page_url())
    context, state = _context_or_state()
    if state:
        blocker = state.get('dependency_blocker')
        return _table_response(
            'analytics/kubernetes/top_consumers/partials/_consumer_detail_results.html',
            {
                'consumer_payload': {'rows': [], 'pagination': {}},
                'render_dependency_blocker': bool(blocker),
                'render_materialization_pending': not bool(blocker),
                **state,
            },
        )

    table_context = context or {}
    dependency_blocker = table_context.get('dependency_blocker')
    if dependency_blocker:
        return _table_response(
            'analytics/kubernetes/top_consumers/partials/_consumer_detail_results.html',
            {
                'consumer_payload': {'rows': [], 'pagination': {}},
                'dependency_blocker': dependency_blocker,
                'render_dependency_blocker': True,
                **{
                    key: value
                    for key, value in table_context.items()
                    if key not in {'consumer_payload', 'dependency_blocker'}
                },
            },
        )
    return _table_response(
        'analytics/kubernetes/top_consumers/partials/_consumer_detail_results.html',
        table_context,
    )
