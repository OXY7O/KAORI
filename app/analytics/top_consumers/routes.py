from __future__ import annotations

from flask import render_template, request

from app.analytics.materialization.presentation import pending_page_context, snapshot_meta
from app.analytics.materialization.requests import resolve_materialized_request
from app.analytics.top_consumers.service import get_top_consumers_context
from app.common.dependencies import render_dependency_blocker
from app.prometheus.repository import resolve_instance_for_cluster
from app.rbac.decorators import permission_required


def _context_or_pending():
    parameters = request.args.to_dict(flat=True)
    parameters.setdefault('time_range', '24h')
    materialized = resolve_materialized_request(
        dataset_key='analytics.top_consumers',
        job_key='analytics.materialize',
        parameters=parameters,
    )
    if materialized.cluster is None or resolve_instance_for_cluster(materialized.cluster.id) is None:
        return get_top_consumers_context(query_args=request.args), None
    if not materialized.result.available:
        return None, pending_page_context(
            materialized=materialized,
            dataset_key='analytics.top_consumers',
            title='Top Consumers',
            description='Consumer rankings are generated once per filter scope and served from a shared snapshot.',
            icon='list-ordered',
        )
    context = materialized.result.context or {}
    context['analytics_materialization'] = snapshot_meta(materialized)
    return context, None


@permission_required('analytics.view')
def top_consumers() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/pending.html', **pending)
    return render_template('analytics/top_consumers/index.html', **(context or {}))


@permission_required('analytics.view')
def top_consumers_section() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/_pending.html', **pending)
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(dependency_blocker)
    return render_template('analytics/top_consumers/partials/_top_consumers_section.html', **(context or {}))


@permission_required('analytics.view')
def top_consumers_table() -> str:
    context, pending = _context_or_pending()
    if pending:
        return render_template('analytics/materialization/_pending.html', **pending)
    dependency_blocker = (context or {}).get('dependency_blocker')
    if dependency_blocker:
        return render_dependency_blocker(dependency_blocker)
    return render_template('analytics/top_consumers/partials/_consumer_detail_section.html', **(context or {}))
