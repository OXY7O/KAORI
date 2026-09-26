from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.audit_correlation import (
    CorrelationCandidate,
    CorrelationChoice,
    NormalizedKubernetesAuditEvent,
    TenantAuditNormalizationError,
    choose_correlation_candidate,
    normalize_kubernetes_audit_event,
    service_account_identity,
)
from app.models import Notification, User
from app.models.tenant import TenantCredential, TenantCredentialType, TenantMembership, TenantNamespace
from app.models.tenant_audit import TenantAuditEvidence
from app.platform_operations.notifications.event_catalog import event_category_key

_EVENT_TYPE = 'kubernetes_tenant_audit'


def _namespace_for_event(cluster_id: str, normalized: NormalizedKubernetesAuditEvent) -> TenantNamespace | None:
    namespace_name = normalized.namespace
    service_account = service_account_identity(normalized.principal_username)
    if namespace_name is None and service_account is not None:
        namespace_name = service_account[0]
    if not namespace_name:
        return None
    return TenantNamespace.query.filter_by(cluster_id=cluster_id, namespace=namespace_name).first()


def _credential_candidates(
    *,
    cluster_id: str,
    normalized: NormalizedKubernetesAuditEvent,
    namespace: TenantNamespace | None,
) -> list[CorrelationCandidate]:
    identity = service_account_identity(normalized.principal_username)
    if identity is None:
        return []
    principal_namespace, service_account_name = identity
    credentials = TenantCredential.query.filter_by(service_account_name=service_account_name).all()
    results: list[CorrelationCandidate] = []
    for credential in credentials:
        if credential.tenant.cluster_id != cluster_id:
            continue
        if namespace is not None and credential.tenant_id != namespace.environment.tenant_id:
            continue
        if namespace is None and credential.anchor_namespace is not None:
            if credential.anchor_namespace.namespace != principal_namespace:
                continue
        results.append(
            CorrelationCandidate(
                credential_id=credential.id,
                credential_public_id=credential.public_id,
                credential_status=credential.status,
                credential_type=credential.credential_type,
                tenant_id=credential.tenant_id,
                namespace_id=namespace.id if namespace is not None else credential.anchor_namespace_id,
                owner_user_id=credential.owner_user_id,
                access_grant_id=credential.access_grant_id,
                application_name=credential.application_name,
                jumpserver_reference=credential.jumpserver_reference,
            )
        )
    return results


def _membership_match(
    *,
    normalized: NormalizedKubernetesAuditEvent,
    namespace: TenantNamespace | None,
) -> tuple[TenantMembership, int | None] | None:
    if namespace is None or service_account_identity(normalized.principal_username) is not None:
        return None
    tenant_id = namespace.environment.tenant_id
    memberships = TenantMembership.query.filter_by(
        tenant_id=tenant_id,
        subject_name=normalized.principal_username,
        status='active',
    ).all()
    matched: list[tuple[TenantMembership, int | None]] = []
    for membership in memberships:
        for grant in membership.access_grants:
            if grant.status != 'active':
                continue
            if grant.scope_type == 'namespace' and grant.tenant_namespace_id == namespace.id:
                matched.append((membership, grant.id))
            elif grant.scope_type == 'environment' and grant.tenant_environment_id == namespace.tenant_environment_id:
                matched.append((membership, grant.id))
            elif grant.scope_type == 'tenant':
                matched.append((membership, grant.id))
    return matched[0] if len(matched) == 1 else None


def correlate_kubernetes_principal(
    *,
    cluster_id: str,
    normalized: NormalizedKubernetesAuditEvent,
) -> tuple[CorrelationChoice, TenantNamespace | None, str]:
    namespace = _namespace_for_event(cluster_id, normalized)
    credential_choice = choose_correlation_candidate(
        _credential_candidates(
            cluster_id=cluster_id,
            normalized=normalized,
            namespace=namespace,
        )
    )
    if credential_choice.status != 'unmanaged':
        identity_class = 'ambiguous'
        if credential_choice.status == 'matched':
            identity_class = {
                TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value: 'human',
                TenantCredentialType.ADMIN_KUBECONFIG.value: 'admin',
                TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT.value: 'cicd',
            }.get(str(credential_choice.credential_type), 'unmanaged')
        return credential_choice, namespace, identity_class

    membership = _membership_match(normalized=normalized, namespace=namespace)
    if membership is not None:
        record, grant_id = membership
        return (
            CorrelationChoice(
                status='matched',
                tenant_id=record.tenant_id,
                namespace_id=namespace.id if namespace is not None else None,
                owner_user_id=record.user_id,
                access_grant_id=grant_id,
            ),
            namespace,
            'group' if record.principal_type == 'group' else 'human',
        )
    return credential_choice, namespace, 'unmanaged'


def _actor_snapshot(
    *,
    evidence: TenantAuditEvidence,
    owner: User | None,
) -> dict[str, object]:
    label = evidence.principal_username
    if evidence.identity_class == 'cicd' and evidence.credential_id is not None:
        label = f'CI/CD · {evidence.principal_username}'
    elif owner is not None and evidence.identity_class in {'human', 'admin'}:
        label = owner.display_name or owner.username
    return {
        'schema': 'activity_actor.v1',
        'key': (
            f'tenant-credential:{evidence.credential_id}'
            if evidence.credential_id is not None
            else f'kubernetes:{evidence.principal_username}'
        ),
        'type': 'service_account' if evidence.principal_kind == 'service_account' else 'external',
        'user_id': evidence.owner_user_id,
        'label': label,
        'email': owner.email if owner is not None else None,
        'role': evidence.identity_class,
        'auth_source': 'kubernetes_audit',
    }


def _project_activity(evidence: TenantAuditEvidence) -> None:
    owner = db.session.get(User, evidence.owner_user_id) if evidence.owner_user_id is not None else None
    activity = Notification()
    activity.user_id = evidence.owner_user_id
    activity.event_type = _EVENT_TYPE
    activity.category_key = event_category_key(_EVENT_TYPE)
    actor = _actor_snapshot(evidence=evidence, owner=owner)
    activity.actor_key = str(actor['key'])
    activity.actor_label = str(actor['label'])
    activity.actor_snapshot_json = actor
    activity.status = 'success' if evidence.outcome == 'success' else ('error' if evidence.outcome == 'failure' else 'info')
    activity.title = 'Kubernetes Tenant API action observed'
    resource = evidence.resource or 'resource'
    scope = evidence.kubernetes_namespace or 'cluster scope'
    activity.message = f'{evidence.principal_username} performed {evidence.verb} on {resource} in {scope}.'
    activity.detail = (
        'KAORI correlated bounded Kubernetes audit evidence to committed Tenant identity state.'
        if evidence.correlation_status == 'matched'
        else 'KAORI retained the Kubernetes principal as explicit unmatched governance evidence.'
    )
    activity.metadata_json = {
        'audit_schema': 'tenant_kubernetes_audit.v1',
        'tenant_audit_evidence_id': evidence.public_id,
        'cluster_id': evidence.cluster_id,
        'tenant_id': evidence.tenant_id,
        'environment_id': evidence.tenant_environment_id,
        'namespace_id': evidence.tenant_namespace_id,
        'namespace': evidence.kubernetes_namespace,
        'principal_username': evidence.principal_username,
        'principal_kind': evidence.principal_kind,
        'identity_class': evidence.identity_class,
        'correlation_status': evidence.correlation_status,
        'credential_id': evidence.credential_id,
        'credential_status': evidence.credential_status,
        'access_grant_id': evidence.access_grant_id,
        'resource_group': evidence.resource_group,
        'resource_version': evidence.resource_version,
        'resource': evidence.resource,
        'subresource': evidence.subresource,
        'resource_name': evidence.resource_name,
        'verb': evidence.verb,
        'response_code': evidence.response_code,
        'outcome': evidence.outcome,
        'event_at': evidence.event_at.isoformat(),
        'source_reference': evidence.source_reference,
        'jumpserver_reference': evidence.jumpserver_reference,
        'secret_material_persisted': False,
    }
    activity.created_at = evidence.observed_at
    activity.deck_visible = False
    activity.read_at = evidence.observed_at
    db.session.add(activity)


def _build_evidence(
    *,
    cluster_id: str,
    normalized: NormalizedKubernetesAuditEvent,
    observed_at: datetime,
) -> TenantAuditEvidence:
    choice, namespace, identity_class = correlate_kubernetes_principal(
        cluster_id=cluster_id,
        normalized=normalized,
    )
    evidence = TenantAuditEvidence()
    evidence.cluster_id = cluster_id
    evidence.tenant_id = choice.tenant_id or (
        namespace.environment.tenant_id if namespace is not None else None
    )
    evidence.tenant_environment_id = namespace.tenant_environment_id if namespace is not None else None
    evidence.tenant_namespace_id = namespace.id if namespace is not None else choice.namespace_id
    evidence.access_grant_id = choice.access_grant_id
    evidence.credential_id = choice.credential_id
    evidence.owner_user_id = choice.owner_user_id
    evidence.source_kind = 'kubernetes_audit'
    evidence.source_event_id = normalized.source_event_id
    evidence.idempotency_key = normalized.idempotency_key
    evidence.source_reference = normalized.source_reference
    evidence.principal_username = normalized.principal_username
    evidence.principal_groups_json = list(normalized.principal_groups)
    evidence.principal_kind = normalized.principal_kind
    evidence.identity_class = identity_class
    evidence.correlation_status = choice.status
    evidence.credential_status = choice.credential_status
    evidence.credential_type = choice.credential_type
    evidence.jumpserver_reference = choice.jumpserver_reference
    evidence.correlation_error = (
        'Multiple managed identity candidates matched the Kubernetes principal.'
        if choice.status == 'ambiguous'
        else None
    )
    evidence.resource_group = normalized.resource_group
    evidence.resource_version = normalized.resource_version
    evidence.resource = normalized.resource
    evidence.subresource = normalized.subresource
    evidence.resource_name = normalized.resource_name
    evidence.kubernetes_namespace = normalized.namespace
    evidence.verb = normalized.verb
    evidence.response_code = normalized.response_code
    evidence.outcome = normalized.outcome
    evidence.event_at = normalized.event_at
    evidence.observed_at = observed_at
    evidence.retention_class = 'tenant_audit_evidence'
    return evidence


def ingest_kubernetes_audit_events_committed(
    *,
    cluster_id: str,
    events: list[dict[str, Any]],
    source_reference: str | None = None,
    observed_at: datetime | None = None,
) -> dict[str, int]:
    observed = (observed_at or datetime.now(UTC)).astimezone(UTC)
    summary = {'received': len(events), 'created': 0, 'duplicate': 0, 'malformed': 0}
    for event in events:
        try:
            normalized = normalize_kubernetes_audit_event(
                event,
                source_reference=source_reference,
            )
        except TenantAuditNormalizationError:
            summary['malformed'] += 1
            continue

        existing = TenantAuditEvidence.query.filter_by(
            cluster_id=cluster_id,
            idempotency_key=normalized.idempotency_key,
        ).first()
        if existing is not None:
            summary['duplicate'] += 1
            continue

        evidence = _build_evidence(
            cluster_id=cluster_id,
            normalized=normalized,
            observed_at=observed,
        )
        db.session.add(evidence)
        try:
            db.session.flush()
            _project_activity(evidence)
            db.session.commit()
            summary['created'] += 1
        except IntegrityError:
            db.session.rollback()
            summary['duplicate'] += 1
        except SQLAlchemyError:
            db.session.rollback()
            raise
    return summary
