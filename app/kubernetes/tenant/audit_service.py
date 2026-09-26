from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.extensions.db import db
from app.kubernetes.tenant.access_reconciliation import target_namespaces
from app.kubernetes.tenant.audit_correlation import (
    NormalizedTenantAuditEvent,
    TenantAuditCorrelationResult,
    TenantAuditPrincipalCandidate,
    correlate_audit_principal,
    normalize_kubernetes_audit_event,
)
from app.kubernetes.tenant.credential import credential_target_namespaces
from app.models import AuditEvent, User
from app.models.tenant import (
    TenantAccessGrant,
    TenantCredential,
    TenantMembership,
    TenantNamespace,
)
from app.models.tenant_audit import TenantKubernetesAuditObservation


def _record_event(
    *,
    actor: User | None,
    target_id: str,
    action: str,
    summary: str,
    metadata: dict[str, object],
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_kubernetes_audit'
    event.target_id = target_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        **metadata,
        'secret_material_persisted': False,
    }
    db.session.add(event)


def _credential_candidates(
    *,
    namespace: TenantNamespace,
    normalized: NormalizedTenantAuditEvent,
) -> list[TenantAuditPrincipalCandidate]:
    if normalized.service_account_name is None:
        return []
    candidates: list[TenantAuditPrincipalCandidate] = []
    credentials = TenantCredential.query.filter_by(
        tenant_id=namespace.environment.tenant_id,
        service_account_name=normalized.service_account_name,
    ).all()
    for credential in credentials:
        if namespace.id not in {item.id for item in credential_target_namespaces(credential)}:
            continue
        grant = credential.access_grant
        membership = grant.membership if grant is not None else None
        candidates.append(
            TenantAuditPrincipalCandidate(
                tenant_id=namespace.environment.tenant_id,
                tenant_environment_id=namespace.tenant_environment_id,
                tenant_namespace_id=namespace.id,
                namespace=namespace.namespace,
                principal_kind='service_account',
                subject_name=credential.service_account_name,
                membership_id=membership.id if membership is not None else None,
                access_grant_id=grant.id if grant is not None else None,
                credential_id=credential.id,
                credential_status=credential.status,
                membership_status=membership.status if membership is not None else None,
                grant_status=grant.status if grant is not None else None,
            )
        )
    return candidates


def _membership_candidates(
    *,
    namespace: TenantNamespace,
    normalized: NormalizedTenantAuditEvent,
) -> list[TenantAuditPrincipalCandidate]:
    subjects = {normalized.username, *normalized.groups}
    memberships = TenantMembership.query.filter(
        TenantMembership.tenant_id == namespace.environment.tenant_id,
        TenantMembership.subject_name.in_(subjects),
    ).all()
    candidates: list[TenantAuditPrincipalCandidate] = []
    for membership in memberships:
        kind = membership.principal_type
        if kind not in {'user', 'group'}:
            continue
        for grant in TenantAccessGrant.query.filter_by(membership_id=membership.id).all():
            if namespace.id not in {item.id for item in target_namespaces(grant)}:
                continue
            candidates.append(
                TenantAuditPrincipalCandidate(
                    tenant_id=namespace.environment.tenant_id,
                    tenant_environment_id=namespace.tenant_environment_id,
                    tenant_namespace_id=namespace.id,
                    namespace=namespace.namespace,
                    principal_kind=kind,
                    subject_name=membership.subject_name,
                    membership_id=membership.id,
                    access_grant_id=grant.id,
                    membership_status=membership.status,
                    grant_status=grant.status,
                )
            )
    return candidates


def _correlate(
    *,
    cluster_id: str,
    normalized: NormalizedTenantAuditEvent,
) -> TenantAuditCorrelationResult:
    if normalized.namespace is None:
        return TenantAuditCorrelationResult(status='unmanaged')
    namespace = TenantNamespace.query.filter_by(
        cluster_id=cluster_id,
        namespace=normalized.namespace,
    ).first()
    if namespace is None:
        return TenantAuditCorrelationResult(status='unmanaged')

    candidates = _credential_candidates(namespace=namespace, normalized=normalized)
    candidates.extend(_membership_candidates(namespace=namespace, normalized=normalized))
    return correlate_audit_principal(normalized, candidates)


def _observation(
    *,
    cluster_id: str,
    normalized: NormalizedTenantAuditEvent,
    correlation: TenantAuditCorrelationResult,
) -> TenantKubernetesAuditObservation:
    observation = TenantKubernetesAuditObservation()
    observation.event_uid = normalized.event_uid
    observation.source_id = normalized.source_id
    observation.cluster_id = cluster_id
    observation.occurred_at = normalized.occurred_at
    observation.username = normalized.username
    observation.principal_kind = correlation.principal_kind
    observation.service_account_namespace = normalized.service_account_namespace
    observation.service_account_name = normalized.service_account_name
    observation.verb = normalized.verb
    observation.api_group = normalized.api_group
    observation.api_version = normalized.api_version
    observation.resource = normalized.resource
    observation.subresource = normalized.subresource
    observation.namespace = normalized.namespace
    observation.resource_name = normalized.resource_name
    observation.response_code = normalized.response_code
    observation.outcome = normalized.outcome
    observation.correlation_status = correlation.status
    observation.tenant_id = correlation.tenant_id
    observation.tenant_environment_id = correlation.tenant_environment_id
    observation.tenant_namespace_id = correlation.tenant_namespace_id
    observation.membership_id = correlation.membership_id
    observation.access_grant_id = correlation.access_grant_id
    observation.credential_id = correlation.credential_id
    observation.correlation_evidence_json = {
        'principal_kind': correlation.principal_kind,
        'subject_name': correlation.subject_name,
        'groups': list(normalized.groups),
        'service_account_namespace': normalized.service_account_namespace,
        'service_account_name': normalized.service_account_name,
        'secret_material_persisted': False,
    }
    observation.expires_at = normalized.expires_at
    return observation


def ingest_kubernetes_audit_event_committed(
    *,
    cluster_id: str,
    source_id: str,
    event: dict[str, Any],
    retention_days: int = 90,
    actor: User | None = None,
) -> TenantKubernetesAuditObservation:
    normalized = normalize_kubernetes_audit_event(
        event,
        source_id=source_id,
        retention_days=retention_days,
    )
    existing = TenantKubernetesAuditObservation.query.filter_by(event_uid=normalized.event_uid).first()
    if existing is not None:
        return existing

    correlation = _correlate(cluster_id=cluster_id, normalized=normalized)
    observation = _observation(
        cluster_id=cluster_id,
        normalized=normalized,
        correlation=correlation,
    )
    db.session.add(observation)
    try:
        db.session.flush()
        _record_event(
            actor=actor,
            target_id=observation.event_uid,
            action='tenant.kubernetes_audit.ingested',
            summary='Normalized Kubernetes audit evidence was correlated with Tenant identity state.',
            metadata={
                'cluster_id': cluster_id,
                'source_id': source_id,
                'occurred_at': normalized.occurred_at.isoformat(),
                'username': normalized.username,
                'namespace': normalized.namespace,
                'verb': normalized.verb,
                'resource': normalized.resource,
                'resource_name': normalized.resource_name,
                'outcome': normalized.outcome,
                'correlation_status': correlation.status,
                'tenant_id': correlation.tenant_id,
                'credential_id': correlation.credential_id,
            },
        )
        db.session.commit()
        return observation
    except IntegrityError:
        db.session.rollback()
        existing = TenantKubernetesAuditObservation.query.filter_by(event_uid=normalized.event_uid).first()
        if existing is not None:
            return existing
        raise


def purge_expired_tenant_audit_observations_committed(
    *,
    now: datetime | None = None,
) -> int:
    cutoff = now or datetime.now(UTC)
    deleted = TenantKubernetesAuditObservation.query.filter(
        TenantKubernetesAuditObservation.expires_at <= cutoff
    ).delete(synchronize_session=False)
    db.session.commit()
    return int(deleted)


def record_kubernetes_audit_source_error_committed(
    *,
    source_id: str,
    message: str,
    actor: User | None = None,
) -> None:
    normalized_source = source_id.strip() or 'unknown'
    safe_message = message.strip()[:500] or 'Kubernetes audit source unavailable.'
    _record_event(
        actor=actor,
        target_id=normalized_source,
        action='tenant.kubernetes_audit.source_error',
        summary='Kubernetes audit evidence source requires operator attention.',
        metadata={
            'source_id': normalized_source,
            'error': safe_message,
        },
    )
    db.session.commit()
