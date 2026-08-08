from __future__ import annotations

from flask import current_app

from app.kubernetes_operations.secrets.reveal_policy import cluster_reveal_readiness
from app.models import Cluster, SecretRevealNamespacePolicy


def build_kubernetes_administration_summary() -> dict[str, object]:
    """Return the lightweight Kubernetes Administration posture projection."""

    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    ready_clusters = sum(cluster_reveal_readiness(cluster) for cluster in clusters)
    enabled_namespaces = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
    ).count()
    return {
        'cluster_count': len(clusters),
        'ready_cluster_count': ready_clusters,
        'enabled_namespace_count': enabled_namespaces,
        'global_reveal_enabled': bool(
            current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False)
        ),
    }
