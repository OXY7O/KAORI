# app/analytics/common/clusters.py

from __future__ import annotations

from app.models import Cluster


def get_selected_cluster(
    clusters: list[Cluster],
    cluster_id: str,
) -> Cluster | None:
    if cluster_id:
        cluster = Cluster.query.filter_by(
            id=cluster_id,
        ).first()

        if cluster:
            return cluster

    if clusters:
        return clusters[0]

    return None
