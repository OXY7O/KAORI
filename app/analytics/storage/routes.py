from __future__ import annotations

from flask import render_template, request

from app.analytics.materialization.presentation import pending_page_context, snapshot_meta
from app.analytics.materialization.requests import resolve_materialized_request
from app.analytics.storage.service import get_storage_analysis_context
from app.common.dependencies import render_dependency_blocker
from app.prometheus.repository import resolve_instance_for_cluster
from app.rbac.decorators import permission_required


def _context_or_pending():
    parameters = request.args.to_dict(flat=True)
    parameters.setdefault('time_range', '24h')
    materialized = resolve_materialized_request(
        dataset_key='analytics.storage',
        job_key='analytics.materialize',
        parameters=parameters,
    )
    if materialized.cluster is None or resolve_instance_for_cluster(materialized.cluster.id) is None:
        return get_storage_analysis_context(query_args=request.args), None
    if not materialized.result.available:
        return None, pending_page_context(
            materialized=materialized,
            dataset_key='analytics.storage',
            title='Storage Analysis',
            description='Storage trends are materialized once and shared across concurrent users.',
            icon='database',
        )
    context = materialized.result.context or {}
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


@permission_required('analytics.view')
def storage() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/pending.html', **pending)
    return render_template('analytics/storage/index.html', **(context or {}))


@permission_required('analytics.view')
def storage_filesystem_summary() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/_pending.html', **pending)
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(dependency_blocker)
    return render_template('analytics/storage/partials/_filesystem_panel.html', **(context or {}))


@permission_required('analytics.view')
def storage_persistent_summary() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/_pending.html', **pending)
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(dependency_blocker)
    return render_template('analytics/storage/partials/_persistent_storage_panel.html', **(context or {}))
