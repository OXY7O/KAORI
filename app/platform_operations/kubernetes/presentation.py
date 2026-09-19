from __future__ import annotations

from flask import current_app

from app.kubernetes.operations.secrets.reveal_policy import cluster_reveal_readiness
from app.models import Cluster, SecretRevealNamespacePolicy


def _administration_posture(
    *,
    cluster_count: int,
    ready_cluster_count: int,
    enabled_namespace_count: int,
    global_reveal_enabled: bool,
) -> tuple[str, str, str]:
    if cluster_count == 0:
        return (
            'Setup Required',
            'warning',
            'Register a Kubernetes connection before configuring protected administration.',
        )
    if not global_reveal_enabled:
        return (
            'Global Gate Disabled',
            'warning',
            'Protected Secret Reveal remains unavailable until the global feature gate is enabled.',
        )
    if ready_cluster_count == 0:
        return (
            'Readiness Review',
            'warning',
            'No connected cluster currently satisfies all Protected Secret Reveal prerequisites.',
        )
    if ready_cluster_count < cluster_count:
        return (
            'Partial Readiness',
            'warning',
            f'{ready_cluster_count} of {cluster_count} connected clusters satisfy reveal prerequisites.',
        )
    if enabled_namespace_count == 0:
        return (
            'Policy Required',
            'warning',
            'Cluster prerequisites are ready; enable at least one namespace policy to admit protected reveal.',
        )
    return (
        'Operational',
        'normal',
        'Protected Secret Reveal has ready cluster and namespace policy coverage.',
    )


def build_kubernetes_administration_summary() -> dict[str, object]:
    """Return the lightweight Kubernetes Administration posture projection."""

    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    ready_clusters = sum(cluster_reveal_readiness(cluster) for cluster in clusters)
    enabled_namespaces = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
    ).count()
    global_reveal_enabled = bool(current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False))
    status_label, status_tone, status_detail = _administration_posture(
        cluster_count=len(clusters),
        ready_cluster_count=ready_clusters,
        enabled_namespace_count=enabled_namespaces,
        global_reveal_enabled=global_reveal_enabled,
    )
    return {
        'cluster_count': len(clusters),
        'ready_cluster_count': ready_clusters,
        'enabled_namespace_count': enabled_namespaces,
        'global_reveal_enabled': global_reveal_enabled,
        'administration_status_label': status_label,
        'administration_status_tone': status_tone,
        'administration_status_detail': status_detail,
    }
