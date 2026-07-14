from __future__ import annotations

from typing import Any

from flask import current_app

from app.models import Cluster, SecretRevealNamespacePolicy
from app.kubernetes_operations.secrets.reveal_policy import (
    REVEAL_NAMESPACE_POLICIES,
    build_namespace_policy_rows,
    cluster_reveal_readiness,
)


def build_secret_reveal_settings_context(
    selected_cluster_id: str | None,
) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    selected_cluster = None
    normalized_cluster_id = (selected_cluster_id or '').strip()

    if normalized_cluster_id:
        selected_cluster = next(
            (cluster for cluster in clusters if cluster.id == normalized_cluster_id),
            None,
        )
    elif clusters:
        selected_cluster = clusters[0]

    namespace_rows: list[dict[str, Any]] = []
    if selected_cluster is not None:
        namespace_rows = build_namespace_policy_rows(selected_cluster)

    total_enabled_namespaces = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
    ).count()
    protected_cluster_count = (
        SecretRevealNamespacePolicy.query.with_entities(
            SecretRevealNamespacePolicy.cluster_id
        )
        .filter(
            SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
        )
        .distinct()
        .count()
    )

    return {
        'clusters': clusters,
        'selected_cluster': selected_cluster,
        'namespace_rows': namespace_rows,
        'reveal_policy_choices': REVEAL_NAMESPACE_POLICIES,
        'global_reveal_enabled': bool(
            current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False)
        ),
        'selected_cluster_ready': bool(
            selected_cluster is not None
            and cluster_reveal_readiness(selected_cluster)
        ),
        'protected_cluster_count': protected_cluster_count,
        'total_enabled_namespaces': total_enabled_namespaces,
        'selected_enabled_namespace_count': sum(
            row['policy'] in {'step_up', 'approval_required'}
            for row in namespace_rows
        ),
    }
