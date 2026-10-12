"""SQL-first, persisted Kubernetes Admin readiness without decrypting fleet kubeconfigs."""

from __future__ import annotations

from sqlalchemy import and_, case, exists, func, or_, select

from app.extensions.db import db
from app.models import Cluster, SecretRevealNamespacePolicy
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.kubernetes import KubernetesConnection

_BLOCKED = ('blocked', 'unavailable', 'disabled', 'incompatible')


def configured_cluster_predicate():
    """Canonical enabled Kubernetes binding; never hydrate encrypted credentials."""
    canonical = IntegrationInstance
    binding = IntegrationBinding
    connection = KubernetesConnection
    return exists(
        select(1)
        .select_from(binding)
        .join(canonical, canonical.id == binding.integration_instance_id)
        .join(connection, connection.integration_instance_id == canonical.id)
        .where(
            binding.asset_type == 'kubernetes_cluster',
            binding.asset_key == Cluster.id,
            binding.enabled.is_(True),
            canonical.integration_type == 'container_orchestrator',
            canonical.enabled.is_(True),
            canonical.lifecycle_status == 'active',
            or_(canonical.readiness_status.is_(None), ~canonical.readiness_status.in_(_BLOCKED)),
            connection.cluster_id == Cluster.id,
            connection.kubeconfig.is_not(None),
        )
    )


def configured_cluster_readiness():
    return and_(
        Cluster.secret_reveal_encryption_verified.is_(True),
        Cluster.secret_reveal_audit_verified.is_(True),
        configured_cluster_predicate(),
    )


def administration_counts() -> dict[str, int]:
    """Configured-prerequisite counters, never live proof of Kubernetes RBAC."""
    ready = configured_cluster_readiness()
    counts = db.session.execute(
        select(
            func.count(Cluster.id),
            func.coalesce(func.sum(case((ready, 1), else_=0)), 0),
        )
    ).one()
    eligible_clusters = select(Cluster.id).where(ready).subquery('eligible_reveal_clusters')
    policy = SecretRevealNamespacePolicy
    enabled = policy.policy.in_(('step_up', 'approval_required'))
    total = db.session.scalar(select(func.count()).select_from(policy).where(enabled))
    eligible = db.session.scalar(
        select(func.count()).select_from(policy)
        .join(eligible_clusters, eligible_clusters.c.id == policy.cluster_id)
        .where(enabled)
    )
    return {
        'cluster_count': int(counts[0]),
        'ready_cluster_count': int(counts[1]),
        'enabled_namespace_count': int(total or 0),
        'eligible_policy_count': int(eligible or 0),
    }
