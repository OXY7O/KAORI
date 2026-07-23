from __future__ import annotations

from app.extensions import db
from app.models import Cluster, NamespaceInventory


def get_clusters_for_filter() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
    ).all()


def get_selected_cluster(
    *,
    cluster_id: str | None,
) -> Cluster | None:
    if cluster_id:
        cluster = db.session.get(
            Cluster,
            cluster_id,
        )

        if cluster is not None:
            return cluster

    return Cluster.query.order_by(
        Cluster.name,
    ).first()


def get_namespace_options(
    *,
    cluster: Cluster | None,
) -> list[str]:
    if cluster is None:
        return []

    namespaces = (
        NamespaceInventory.query.filter_by(
            cluster_id=cluster.id,
        )
        .order_by(
            NamespaceInventory.namespace,
        )
        .all()
    )

    return [namespace.namespace for namespace in namespaces if namespace.namespace]
