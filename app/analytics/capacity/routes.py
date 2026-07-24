from __future__ import annotations

from flask import render_template, request

from app.analytics.capacity.service import get_capacity_page_context
from app.analytics.common.presentation import present_capacity_context
from app.analytics.materialization.presentation import pending_page_context, snapshot_meta
from app.analytics.materialization.requests import resolve_materialized_request
from app.prometheus.repository import resolve_instance_for_cluster
from app.rbac.decorators import permission_required


@permission_required('analytics.view')
def capacity() -> str:
    parameters = request.args.to_dict(flat=True)
    parameters.setdefault('time_range', '24h')
    materialized = resolve_materialized_request(
        dataset_key='analytics.capacity',
        job_key='analytics.materialize',
        parameters=parameters,
    )
    if materialized.cluster is None or resolve_instance_for_cluster(materialized.cluster.id) is None:
        context = present_capacity_context(get_capacity_page_context(query_args=request.args))
        return render_template('analytics/capacity/index.html', **context)
    if not materialized.result.available:
        return render_template(
            'analytics/materialization/pending.html',
            **pending_page_context(
                materialized=materialized,
                dataset_key='analytics.capacity',
                title='Capacity Analysis',
                description='KAORI prepares shared capacity results before serving long-range analytics.',
                icon='server-cog',
            ),
        )
    context = present_capacity_context(materialized.result.context or {})
    context['analytics_materialization'] = snapshot_meta(materialized)
    return render_template('analytics/capacity/index.html', **context)
