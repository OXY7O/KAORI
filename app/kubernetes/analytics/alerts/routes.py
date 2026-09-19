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
from app.kubernetes.analytics.alerts.application import present_alerts_materialized_context
from app.kubernetes.analytics.alerts.contracts import SOURCE_OPTIONS, AlertsSelection, normalize_option
from app.kubernetes.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.kubernetes.analytics.materialization.requests import resolve_materialized_request

_ALERT_TABS = {
    'alerts',
    'anomalies',
    'routing',
    'ownership',
    'readiness',
    'recommendations',
    'resources',
}

_PAGE = {
    'dataset_key': 'analytics.alerts',
    'title': 'Alerts & Anomalies',
    'description': 'Alertmanager and Metrics Source signals are collected by analytics workers for shared KAORI use.',
    'icon': 'siren',
    'page_id': 'alerts-page-content',
}


def _selected_tab() -> str:
    value = str(request.args.get('tab') or 'alerts').strip().lower()
    return value if value in _ALERT_TABS else 'alerts'


def _snapshot_parameters() -> dict[str, str]:
    """Alert snapshots vary only by cluster and selected provider source."""
    parameters: dict[str, str] = {
        'source': normalize_option(
            request.args.get('source'),
            allowed=SOURCE_OPTIONS,
            default='auto',
        )
    }
    cluster_id = request.args.get('cluster_id', type=str)
    if cluster_id:
        parameters['cluster_id'] = cluster_id
    return parameters


def _present(materialized):
    context = present_alerts_materialized_context(
        materialized.result.context or {},
        AlertsSelection(
            severity=request.args.get('severity'),
            status=request.args.get('status'),
            namespace=request.args.get('namespace'),
            search=request.args.get('search'),
            alerts_page=request.args.get('alerts_page', '1'),
            anomalies_page=request.args.get('anomalies_page', '1'),
            alerts_per_page=request.args.get('alerts_per_page', request.args.get('per_page', '5')),
            anomalies_per_page=request.args.get('anomalies_per_page', request.args.get('per_page', '5')),
        ),
    )
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['selected_tab'] = _selected_tab()
    return context


def _context_or_state():
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters=_snapshot_parameters(),
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = _present(materialized)
            context['dependency_blocker'] = materialized.dependency_blocker
            return context, None
        return None, blocked_page_context(
            materialized=materialized,
            **{key: value for key, value in _PAGE.items() if key != 'dataset_key'},
        )
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    return _present(materialized), None


def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request', '').lower() == 'true'


def _full_page_url(tab: str) -> str:
    query_args: dict[str, Any] = request.args.to_dict(flat=True)
    query_args['tab'] = tab
    return url_for('analytics.alerts', **query_args)


def _fragment_response(payload: ResponseReturnValue, *, tab: str) -> Response:
    response = make_response(payload)
    response.headers['HX-Push-Url'] = _full_page_url(tab)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


def _table_payload(*, template: str, tab: str) -> Response:
    context, state = _context_or_state()
    if state:
        blocker = state.get('dependency_blocker')
        payload = (
            render_dependency_blocker(blocker)
            if blocker
            else render_template('kubernetes/analytics/materialization/_pending.html', **state)
        )
        return _fragment_response(payload, tab=tab)

    table_context = context or {}
    dependency_blocker = table_context.get('dependency_blocker')
    if dependency_blocker:
        return _fragment_response(
            render_dependency_blocker(dependency_blocker),
            tab=tab,
        )
    return _fragment_response(render_template(template, **table_context), tab=tab)


@permission_required('analytics.view')
def alerts() -> ResponseReturnValue:
    context, state = _context_or_state()
    if state:
        template = (
            'kubernetes/analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'kubernetes/analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('kubernetes/analytics/alerts/index.html', **(context or {}))


@permission_required('analytics.view')
def alerts_table() -> ResponseReturnValue:
    if not _is_htmx_request():
        return redirect(_full_page_url('alerts'))
    return _table_payload(
        template='kubernetes/analytics/alerts/partials/_alerts_table.html',
        tab='alerts',
    )


@permission_required('analytics.view')
def anomalies_table() -> ResponseReturnValue:
    if not _is_htmx_request():
        return redirect(_full_page_url('anomalies'))
    return _table_payload(
        template='kubernetes/analytics/alerts/partials/_anomalies_table.html',
        tab='anomalies',
    )
