from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver import (
    kubeconfig_for_cluster,
)
from app.kubernetes_operations.secrets.live_service import (
    list_live_namespaces,
    list_verified_namespaces,
    verify_live_namespace,
)
from app.models import Cluster, SecretRevealNamespacePolicy, SecretRevealRequest

REVEAL_NAMESPACE_POLICIES = {
    'disabled': 'Disabled',
    'step_up': 'Step-up authentication',
    'approval_required': 'Approval required',
}
ENABLED_REVEAL_NAMESPACE_POLICIES = {'step_up', 'approval_required'}

_NAMESPACE_SOURCE_CACHE: dict[str, NamespaceSourceSnapshot] = {}
_NAMESPACE_SOURCE_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class NamespaceRevealPolicyChange:
    cluster: Cluster
    namespace: str
    previous_policy: str
    policy: str
    record: SecretRevealNamespacePolicy | None


@dataclass(frozen=True)
class NamespaceSourceSnapshot:
    cluster_id: str
    names: tuple[str, ...]
    state: str
    last_attempted_at: datetime
    last_successful_at: datetime | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.state == 'available'


def normalize_namespace_policy(value: str | None) -> str:
    normalized = (value or 'disabled').strip().lower()
    if normalized not in REVEAL_NAMESPACE_POLICIES:
        raise ValueError('Unsupported Protected Secret Reveal namespace policy.')
    return normalized


def cluster_reveal_readiness_evidence(cluster: Cluster) -> dict[str, bool]:
    try:
        credential_configured = bool(kubeconfig_for_cluster(cluster))
    except (RuntimeError, ValueError):
        credential_configured = False
    encryption_verified = bool(cluster.secret_reveal_encryption_verified)
    audit_verified = bool(cluster.secret_reveal_audit_verified)
    return {
        'credential_configured': credential_configured,
        'encryption_verified': encryption_verified,
        'audit_verified': audit_verified,
        'ready': bool(credential_configured and encryption_verified and audit_verified),
    }


def cluster_reveal_readiness(cluster: Cluster) -> bool:
    return cluster_reveal_readiness_evidence(cluster)['ready']


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


def get_configured_enabled_namespace_names(cluster_id: str) -> list[str]:
    return sorted({record.namespace for record in get_enabled_namespace_policy_records(cluster_id)})


def get_enabled_namespace_names(cluster_id: str) -> list[str]:
    """Return configured Reveal namespaces that can be verified live with namespace GET."""
    configured = get_configured_enabled_namespace_names(cluster_id)
    if not configured:
        return []
    return list_verified_namespaces(cluster_id, configured)


def refresh_namespace_source_snapshot(cluster: Cluster) -> NamespaceSourceSnapshot:
    cluster_id = str(cluster.id)
    attempted_at = datetime.now(UTC)
    with _NAMESPACE_SOURCE_CACHE_LOCK:
        previous = _NAMESPACE_SOURCE_CACHE.get(cluster_id)

    try:
        names = tuple(sorted(set(list_live_namespaces(cluster_id))))
    except ValueError as exc:
        snapshot = NamespaceSourceSnapshot(
            cluster_id=cluster_id,
            names=previous.names if previous is not None else (),
            state='unavailable',
            last_attempted_at=attempted_at,
            last_successful_at=previous.last_successful_at if previous is not None else None,
            error=str(exc),
        )
    else:
        snapshot = NamespaceSourceSnapshot(
            cluster_id=cluster_id,
            names=names,
            state='available',
            last_attempted_at=attempted_at,
            last_successful_at=attempted_at,
            error=None,
        )

    with _NAMESPACE_SOURCE_CACHE_LOCK:
        _NAMESPACE_SOURCE_CACHE[cluster_id] = snapshot
    return snapshot


def get_namespace_source_snapshot(
    cluster: Cluster,
    *,
    refresh: bool = False,
) -> NamespaceSourceSnapshot:
    cluster_id = str(cluster.id)
    if refresh:
        return refresh_namespace_source_snapshot(cluster)

    with _NAMESPACE_SOURCE_CACHE_LOCK:
        cached = _NAMESPACE_SOURCE_CACHE.get(cluster_id)
    if cached is not None:
        return cached
    return refresh_namespace_source_snapshot(cluster)


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

    existing = get_namespace_policy_record(cluster.id, normalized_namespace)
    normalized_policy = normalize_namespace_policy(policy)
    previous_policy = existing.policy if existing is not None else 'disabled'

    if normalized_policy != 'disabled':
        verify_live_namespace(cluster, normalized_namespace)

    if normalized_policy in ENABLED_REVEAL_NAMESPACE_POLICIES and not cluster_reveal_readiness(cluster):
        raise ValueError(
            'Configure the cluster credential and verify Secret encryption at rest and Metadata-level audit logging before enabling a namespace.'
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
        existing = SecretRevealNamespacePolicy()
        existing.cluster_id = cluster.id
        existing.namespace = normalized_namespace
        existing.policy = normalized_policy
        existing.created_by_user_id = actor_user_id
        existing.updated_by_user_id = actor_user_id
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


def build_namespace_policy_rows(
    cluster: Cluster,
    *,
    refresh_source: bool = False,
) -> tuple[list[dict[str, Any]], NamespaceSourceSnapshot]:
    policy_records = {
        record.namespace: record for record in SecretRevealNamespacePolicy.query.filter_by(cluster_id=cluster.id).all()
    }
    source_snapshot = get_namespace_source_snapshot(cluster, refresh=refresh_source)
    source_names = set(source_snapshot.names)
    names = sorted(source_names.union(policy_records))

    rows: list[dict[str, Any]] = []
    for namespace in names:
        policy = policy_records[namespace].policy if namespace in policy_records else 'disabled'
        if not source_snapshot.available:
            live_state = 'unknown'
        elif namespace in source_names:
            live_state = 'available'
        else:
            live_state = 'missing'
        rows.append(
            {
                'namespace': namespace,
                'policy': policy,
                'policy_label': REVEAL_NAMESPACE_POLICIES.get(policy, 'Disabled'),
                'in_live_cluster': live_state == 'available',
                'live_state': live_state,
                'record': policy_records.get(namespace),
            }
        )
    return rows, source_snapshot
