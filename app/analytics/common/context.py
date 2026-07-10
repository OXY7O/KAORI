# app/analytics/common/context.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.analytics.common.clusters import get_selected_cluster
from app.analytics.common.params import (
    get_query_value,
    get_selected_time_range,
)
from app.analytics.utilization.service import UtilizationService
from app.models import Cluster
from app.prometheus.service import PrometheusService


def get_default_prometheus_status() -> dict[str, Any]:
    return {
        'connected': False,
        'response_time_ms': None,
        'label': 'Prometheus Disconnected',
        'description': 'Prometheus unavailable',
    }


def build_analysis_utilization_context(
    query_args: Mapping[str, Any],
) -> tuple[list[Cluster], Cluster | None, UtilizationService | None, dict[str, Any]]:
    clusters = Cluster.query.order_by(
        Cluster.name,
    ).all()

    cluster_id = get_query_value(
        query_args=query_args,
        name='cluster_id',
        default='',
    )

    cluster = get_selected_cluster(
        clusters=clusters,
        cluster_id=cluster_id,
    )

    base_context: dict[str, Any] = {
        'clusters': clusters,
        'cluster': cluster,
        'error': None,
        'prometheus_connected': False,
        'prometheus_status': get_default_prometheus_status(),
        'selected_namespace': get_query_value(
            query_args=query_args,
            name='namespace',
            default='',
        ),
        'selected_time_range': get_selected_time_range(
            query_args=query_args,
        ),
    }

    if cluster is None:
        return clusters, None, None, base_context

    prometheus = PrometheusService(
        cluster,
    )

    utilization_service = UtilizationService(
        prometheus,
    )

    return clusters, cluster, utilization_service, base_context
