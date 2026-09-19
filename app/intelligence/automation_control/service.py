from __future__ import annotations

from collections.abc import Sequence

from flask import current_app

from app.extensions.db import db
from app.integrations.resolver_bootstrap import get_resolver_registry
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceDecision, IntelligenceDecisionCandidate
from app.models.knowledge import KnowledgeRunbook, KnowledgeRunbookAlertBinding, KnowledgeRunbookRevision
from app.models.resolver import ResolverDeploymentPolicy, ResolverProductionReadinessRecord


def get_runbook(runbook_id: int) -> KnowledgeRunbook | None:
    return db.session.get(KnowledgeRunbook, runbook_id)


def get_runbook_revision(revision_id: int) -> KnowledgeRunbookRevision | None:
    return db.session.get(KnowledgeRunbookRevision, revision_id)


def get_runbook_binding(binding_id: int) -> KnowledgeRunbookAlertBinding | None:
    return db.session.get(KnowledgeRunbookAlertBinding, binding_id)


def get_decision_candidate(candidate_id: int) -> IntelligenceDecisionCandidate | None:
    return db.session.get(IntelligenceDecisionCandidate, candidate_id)


def get_decision(decision_id: int) -> IntelligenceDecision | None:
    return db.session.get(IntelligenceDecision, decision_id)


def get_cluster(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_readiness_record(record_id: int) -> ResolverProductionReadinessRecord | None:
    return db.session.get(ResolverProductionReadinessRecord, record_id)


def commit_automation_control() -> None:
    db.session.commit()


def rollback_automation_control() -> None:
    db.session.rollback()


def upsert_deployment_policy(
    *,
    cluster_id: str,
    action_key: str,
    lifecycle_status: str,
    allowed_namespaces: Sequence[str],
    required_registry_fingerprint: str | None,
    actor_user_id: int | None,
) -> ResolverDeploymentPolicy:
    if lifecycle_status not in {'active', 'disabled'}:
        raise ValueError('Deployment policy status must be active or disabled.')
    cluster = get_cluster(cluster_id)
    if cluster is None:
        raise ValueError('Selected cluster does not exist.')
    registry = get_resolver_registry(current_app)
    registry.describe(action_key)
    current_fingerprint = str(current_app.config.get('RESOLVER_REGISTRY_FINGERPRINT') or '').strip()
    requested_fingerprint = str(required_registry_fingerprint or '').strip()
    if requested_fingerprint and requested_fingerprint != current_fingerprint:
        raise ValueError('Required registry fingerprint does not match the current KAORI resolver registry.')
    pinned_fingerprint = requested_fingerprint or current_fingerprint or None
    namespaces = sorted({item.strip() for item in allowed_namespaces if item.strip()})
    if lifecycle_status == 'active' and not namespaces:
        raise ValueError('An active resolver deployment policy requires an explicit namespace allowlist.')

    record = ResolverDeploymentPolicy.query.filter_by(cluster_id=cluster_id, action_key=action_key).one_or_none()
    created = record is None
    if record is None:
        record = ResolverDeploymentPolicy()
        record.cluster_id = cluster_id
        record.action_key = action_key
        record.created_by_user_id = actor_user_id
        db.session.add(record)
    record.lifecycle_status = lifecycle_status
    record.allowed_namespaces_json = namespaces
    record.required_registry_fingerprint = pinned_fingerprint
    record.updated_by_user_id = actor_user_id

    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'resolver_deployment_policy'
    event.target_id = f'{cluster_id}:{action_key}'
    event.action = 'resolver.deployment_policy.created' if created else 'resolver.deployment_policy.updated'
    event.summary = 'KAORI resolver deployment policy updated.'
    event.metadata_json = {
        'cluster_id': cluster_id,
        'action_key': action_key,
        'lifecycle_status': lifecycle_status,
        'allowed_namespaces': namespaces,
        'required_registry_fingerprint': record.required_registry_fingerprint,
    }
    db.session.add(event)
    db.session.commit()
    return record
