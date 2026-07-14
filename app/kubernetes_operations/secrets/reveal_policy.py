from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions import db
from app.models import (
    Cluster,
    NamespaceInventory,
    SecretRevealNamespacePolicy,
    SecretRevealRequest,
)

REVEAL_NAMESPACE_POLICIES = {
    'disabled': 'Disabled',
    'step_up': 'Step-up authentication',
    'approval_required': 'Approval required',
}
ENABLED_REVEAL_NAMESPACE_POLICIES = {'step_up', 'approval_required'}


@dataclass(frozen=True)
class NamespaceRevealPolicyChange:
    cluster: Cluster
    namespace: str
    previous_policy: str
    policy: str
    record: SecretRevealNamespacePolicy | None


def normalize_namespace_policy(value: str | None) -> str:
    normalized = (value or 'disabled').strip().lower()
    if normalized not in REVEAL_NAMESPACE_POLICIES:
        raise ValueError('Unsupported Protected Secret Reveal namespace policy.')
    return normalized


def cluster_reveal_readiness(cluster: Cluster) -> bool:
    return bool(
        cluster.kubeconfig
        and cluster.secret_reveal_encryption_verified
        and cluster.secret_reveal_audit_verified
    )


def get_namespace_policy_record(
    cluster_id: str,
    namespace: str,
) -> SecretRevealNamespacePolicy | None:
    return SecretRevealNamespacePolicy.query.filter_by(
        cluster_id=cluster_id,
        namespace=namespace,
    ).first()


def get_namespace_policy(cluster_id: str, namespace: str) -> str:
    record = get_namespace_policy_record(cluster_id, namespace)
    return record.policy if record is not None else 'disabled'


def namespace_reveal_enabled(cluster_id: str, namespace: str) -> bool:
    return get_namespace_policy(cluster_id, namespace) in ENABLED_REVEAL_NAMESPACE_POLICIES


def get_enabled_namespace_policy_records(
    cluster_id: str | None = None,
) -> list[SecretRevealNamespacePolicy]:
    query = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(tuple(ENABLED_REVEAL_NAMESPACE_POLICIES))
    )
    if cluster_id:
        query = query.filter(SecretRevealNamespacePolicy.cluster_id == cluster_id)
    return query.order_by(
        SecretRevealNamespacePolicy.cluster_id.asc(),
        SecretRevealNamespacePolicy.namespace.asc(),
    ).all()


def get_enabled_namespace_names(cluster_id: str) -> list[str]:
    configured = {
        record.namespace
        for record in get_enabled_namespace_policy_records(cluster_id)
    }
    if not configured:
        return []
    inventory_names = {
        value
        for (value,) in (
            NamespaceInventory.query.with_entities(NamespaceInventory.namespace)
            .filter(
                NamespaceInventory.cluster_id == cluster_id,
                NamespaceInventory.namespace.in_(tuple(configured)),
            )
            .distinct()
            .all()
        )
    }
    return sorted(configured.intersection(inventory_names))


def update_cluster_reveal_readiness(
    cluster: Cluster,
    *,
    encryption_verified: bool,
    audit_verified: bool,
) -> Cluster:
    cluster.secret_reveal_encryption_verified = bool(encryption_verified)
    cluster.secret_reveal_audit_verified = bool(audit_verified)
    if not cluster_reveal_readiness(cluster):
        SecretRevealRequest.query.filter(
            SecretRevealRequest.cluster_id == cluster.id,
            SecretRevealRequest.status.in_(('pending', 'approved')),
        ).update(
            {'status': 'expired'},
            synchronize_session=False,
        )
    db.session.commit()
    return cluster


def set_namespace_reveal_policy(
    cluster: Cluster,
    namespace: str | None,
    policy: str | None,
    *,
    actor_user_id: int | None,
) -> NamespaceRevealPolicyChange:
    normalized_namespace = (namespace or '').strip()
    if not normalized_namespace:
        raise ValueError('Namespace is required.')

    namespace_exists = (
        NamespaceInventory.query.filter_by(
            cluster_id=cluster.id,
            namespace=normalized_namespace,
        ).first()
        is not None
    )
    existing = get_namespace_policy_record(cluster.id, normalized_namespace)
    if not namespace_exists and existing is None:
        raise ValueError(
            'The selected namespace is not available in the latest inventory snapshot. Run inventory sync before configuring Reveal access.'
        )

    normalized_policy = normalize_namespace_policy(policy)
    previous_policy = existing.policy if existing is not None else 'disabled'

    if normalized_policy in ENABLED_REVEAL_NAMESPACE_POLICIES and not cluster_reveal_readiness(cluster):
        raise ValueError(
            'Verify Kubernetes Secret encryption at rest and Metadata-level audit logging for this cluster before enabling a namespace.'
        )

    if normalized_policy != previous_policy:
        SecretRevealRequest.query.filter(
            SecretRevealRequest.cluster_id == cluster.id,
            SecretRevealRequest.namespace == normalized_namespace,
            SecretRevealRequest.status.in_(('pending', 'approved')),
        ).update(
            {'status': 'expired'},
            synchronize_session=False,
        )

    if normalized_policy == 'disabled':
        if existing is not None:
            db.session.delete(existing)
        db.session.commit()
        return NamespaceRevealPolicyChange(
            cluster=cluster,
            namespace=normalized_namespace,
            previous_policy=previous_policy,
            policy='disabled',
            record=None,
        )

    if existing is None:
        existing = SecretRevealNamespacePolicy(
            cluster_id=cluster.id,
            namespace=normalized_namespace,
            policy=normalized_policy,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        db.session.add(existing)
    else:
        existing.policy = normalized_policy
        existing.updated_by_user_id = actor_user_id

    db.session.commit()
    return NamespaceRevealPolicyChange(
        cluster=cluster,
        namespace=normalized_namespace,
        previous_policy=previous_policy,
        policy=normalized_policy,
        record=existing,
    )


def build_namespace_policy_rows(cluster: Cluster) -> list[dict[str, Any]]:
    inventory_names = {
        value
        for (value,) in (
            NamespaceInventory.query.with_entities(NamespaceInventory.namespace)
            .filter(NamespaceInventory.cluster_id == cluster.id)
            .distinct()
            .order_by(NamespaceInventory.namespace.asc())
            .all()
        )
    }
    policy_records = {
        record.namespace: record
        for record in SecretRevealNamespacePolicy.query.filter_by(cluster_id=cluster.id).all()
    }
    names = sorted(inventory_names.union(policy_records))
    return [
        {
            'namespace': namespace,
            'policy': (
                policy_records[namespace].policy
                if namespace in policy_records
                else 'disabled'
            ),
            'policy_label': REVEAL_NAMESPACE_POLICIES.get(
                policy_records[namespace].policy
                if namespace in policy_records
                else 'disabled',
                'Disabled',
            ),
            'in_inventory': namespace in inventory_names,
            'record': policy_records.get(namespace),
        }
        for namespace in names
    ]
