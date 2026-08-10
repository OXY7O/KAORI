from __future__ import annotations

from typing import Any

from app.cluster.constants import get_environment_label
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.report import Report
from app.reports.catalog import ReportContractError, require_selected_cluster


def get_report_selected_cluster(report: Report) -> Cluster:
    """Resolve exactly the cluster stored on the report; never choose a fallback."""

    cluster_id = require_selected_cluster(report)
    cluster = db.session.get(Cluster, cluster_id)
    if cluster is None:
        raise ReportContractError(f'The selected Kubernetes cluster {cluster_id!r} no longer exists.')
    return cluster


def serialize_report_cluster(cluster: Any | None) -> dict[str, str] | None:
    """Return the selected-cluster identity without touching provider services."""

    if cluster is None:
        return None
    return {
        'id': str(getattr(cluster, 'id', '') or ''),
        'name': str(getattr(cluster, 'name', 'Unknown Cluster') or 'Unknown Cluster'),
        'environment': get_environment_label(
            getattr(cluster, 'environment', None),
            empty='',
        ),
        'status': str(getattr(cluster, 'status', '') or ''),
    }


def report_payload_error(exc: Exception, *, cluster: Any | None = None) -> dict[str, Any]:
    """Preserve the selected-cluster boundary when a provider payload fails."""

    payload: dict[str, Any] = {'_error': str(exc)}
    cluster_payload = serialize_report_cluster(cluster)
    if cluster_payload is not None:
        payload['cluster'] = cluster_payload
    return payload
