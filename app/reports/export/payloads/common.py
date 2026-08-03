from __future__ import annotations

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.report import Report
from app.reports.catalog import ReportContractError, require_selected_cluster


def get_report_selected_cluster(report: Report) -> Cluster:
    """Resolve exactly the cluster stored on the report; never choose a fallback."""

    cluster_id = require_selected_cluster(report)
    cluster = db.session.get(Cluster, cluster_id)
    if cluster is None:
        raise ReportContractError(
            f'The selected Kubernetes cluster {cluster_id!r} no longer exists.'
        )
    return cluster
