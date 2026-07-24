from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from flask import request, url_for

from app.analytics.materialization.requests import MaterializedRequest


def snapshot_meta(materialized: MaterializedRequest) -> dict[str, Any]:
    snapshot = materialized.result.snapshot
    return {
        'state': materialized.result.state,
        'stale': materialized.result.stale,
        'refresh_dispatched': materialized.dispatched,
        'generated_at': snapshot.generated_at if snapshot else None,
        'expires_at': snapshot.expires_at if snapshot else None,
        'last_error': snapshot.last_error if snapshot else None,
    }


def pending_page_context(
    *,
    materialized: MaterializedRequest,
    dataset_key: str,
    title: str,
    description: str,
    icon: str,
) -> dict[str, Any]:
    parameters = dict(materialized.parameters)
    return_url = request.full_path.rstrip('?')
    status_query = urlencode(
        {
            'dataset_key': dataset_key,
            'cluster_id': materialized.cluster.id if materialized.cluster else '',
            'return_url': return_url,
            **parameters,
        }
    )
    snapshot = materialized.result.snapshot
    return {
        'materialization_title': title,
        'materialization_description': description,
        'materialization_icon': icon,
        'materialization_cluster': materialized.cluster,
        'materialization_state': materialized.result.state,
        'materialization_error': materialized.dispatch_error or (snapshot.last_error if snapshot else None),
        'materialization_status_url': f'{url_for("analytics.materialization_status")}?{status_query}',
        'materialization_return_url': return_url,
    }
