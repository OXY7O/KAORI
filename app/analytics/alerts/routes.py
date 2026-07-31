from __future__ import annotations

from flask import render_template, request
from flask.typing import ResponseReturnValue

from app.analytics.alerts.application import present_alerts_materialized_context
from app.analytics.materialization.presentation import (
    blocked_page_context,
    pending_page_context,
    snapshot_meta,
)
from app.analytics.materialization.requests import resolve_materialized_request
from app.common.dependencies import render_dependency_blocker
from app.rbac.decorators import permission_required



_ALERT_TABS = {
    'alerts',
    'anomalies',
    'routing',
    'ownership',
    'readiness',
    'recommendations',
    'resources',
}


def _selected_tab() -> str:
    value = str(request.args.get('tab') or 'alerts').strip().lower()
    return value if value in _ALERT_TABS else 'alerts'

_PAGE = {
    'dataset_key': 'analytics.alerts',
    'title': 'Alerts & Anomalies',
    'description': (
        'Alertmanager and Prometheus signals are collected by the analytics worker '
        'and shared across concurrent viewers.'
    ),
    'icon': 'siren',
    'page_id': 'alerts-page-content',
}


def _present(materialized):
    context = present_alerts_materialized_context(
        materialized.result.context or {},
        severity=request.args.get('severity'),
        status=request.args.get('status'),
        namespace=request.args.get('namespace'),
        search=request.args.get('search'),
        page=request.args.get('page', '1'),
        alerts_per_page=request.args.get('alerts_per_page', request.args.get('per_page', '5')),
        anomalies_per_page=request.args.get('anomalies_per_page', request.args.get('per_page', '5')),
    )
    context['analytics_materialization'] = snapshot_meta(materialized)
    context['selected_tab'] = _selected_tab()
    return context


def _context_or_state():
    source = request.args.get('source') or 'auto'
    materialized = resolve_materialized_request(
        dataset_key=_PAGE['dataset_key'],
        job_key='analytics.materialize',
        parameters={'cluster_id': request.args.get('cluster_id', ''), 'source': source},
    )
    if materialized.dependency_blocker:
        if materialized.result.available:
            context = _present(materialized)
            context['dependency_blocker'] = materialized.dependency_blocker
            return context, None
        return None, blocked_page_context(materialized=materialized, **{k: v for k, v in _PAGE.items() if k != 'dataset_key'})
    if not materialized.result.available:
        return None, pending_page_context(materialized=materialized, **_PAGE)
    return _present(materialized), None


@permission_required('analytics.view')
def alerts() -> ResponseReturnValue:
    context, state = _context_or_state()
    if state:
        template = (
            'analytics/materialization/blocked.html'
            if state.get('dependency_blocker')
            else 'analytics/materialization/pending.html'
        )
        return render_template(template, **state)
    return render_template('analytics/alerts/index.html', **(context or {}))


@permission_required('analytics.view')
def alerts_table() -> ResponseReturnValue:
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
    return render_template('analytics/alerts/partials/_alerts_table.html', **(context or {}))


@permission_required('analytics.view')
def anomalies_table() -> ResponseReturnValue:
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
    return render_template('analytics/alerts/partials/_anomalies_table.html', **(context or {}))
