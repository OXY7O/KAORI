from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from app.definitions.loader import load_definition_document
from app.definitions.validation import string_tuple
from app.extensions.db import db
from app.models.audit import AuditEvent
from app.models.resolver import ResolverDeploymentPolicy, ResolverOperationalControl, ResolverProductionReadinessRecord

_READINESS_DEFINITION = load_definition_document(
    'intelligence/automation/production_readiness.yaml',
    expected_kind='automation_production_readiness',
)
REQUIRED_CHECKS = string_tuple(_READINESS_DEFINITION.get('required_checks'), 'required_checks')
STAGE_ORDER = string_tuple(_READINESS_DEFINITION.get('rollout_stages'), 'rollout_stages')


class ProductionReadinessError(RuntimeError):
    """Raised when controlled rollout safety gates are incomplete or inconsistent."""


def assert_deployment_policy_allows(
    *,
    cluster_id: str,
    namespace: str | None,
    action_key: str,
    registry_fingerprint: str,
) -> ResolverDeploymentPolicy:
    policy = ResolverDeploymentPolicy.query.filter_by(
        cluster_id=cluster_id,
        action_key=action_key,
    ).one_or_none()
    if policy is None or policy.lifecycle_status != 'active':
        raise ProductionReadinessError('Resolver deployment policy is not active for this cluster and action.')

    allowed_namespaces = {str(item).strip() for item in (policy.allowed_namespaces_json or []) if str(item).strip()}
    normalized_namespace = str(namespace or '').strip()
    if not normalized_namespace or normalized_namespace not in allowed_namespaces:
        raise ProductionReadinessError('Resolver target namespace is not allowed by deployment policy.')

    required_fingerprint = str(policy.required_registry_fingerprint or '').strip()
    if required_fingerprint and required_fingerprint != registry_fingerprint:
        raise ProductionReadinessError('Resolver registry fingerprint does not match deployment policy.')
    return policy


@dataclass(frozen=True, slots=True)
class ReadinessAssessment:
    ready: bool
    failed_checks: tuple[str, ...]
    evidence_hash: str
    rollout_stage: str


def canonical_evidence_hash(results: Mapping[str, object]) -> str:
    payload = json.dumps(dict(results), sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def assess_readiness(*, results: Mapping[str, object], rollout_stage: str = 'disabled') -> ReadinessAssessment:
    unknown = sorted(set(results) - set(REQUIRED_CHECKS))
    if unknown:
        raise ProductionReadinessError(f'Unknown production readiness checks: {", ".join(unknown)}.')
    failed = tuple(name for name in REQUIRED_CHECKS if results.get(name) is not True)
    return ReadinessAssessment(
        ready=not failed,
        failed_checks=failed,
        evidence_hash=canonical_evidence_hash(results),
        rollout_stage=rollout_stage,
    )


def record_validation(
    *,
    cluster_id: str,
    action_key: str,
    results: Mapping[str, object],
    actor_user_id: int | None,
) -> ResolverProductionReadinessRecord:
    assessment = assess_readiness(results=results)
    record = ResolverProductionReadinessRecord.query.filter_by(
        cluster_id=cluster_id,
        action_key=action_key,
    ).one_or_none()
    if record is None:
        record = ResolverProductionReadinessRecord()
        record.cluster_id = cluster_id
        record.action_key = action_key
        db.session.add(record)
    record.validation_results_json = dict(results)
    record.evidence_hash = assessment.evidence_hash
    record.validated_at = datetime.now(UTC)
    record.validated_by_user_id = actor_user_id
    record.approved_at = None
    record.approved_by_user_id = None
    if record.rollout_stage == 'production' and not assessment.ready:
        record.rollout_stage = 'disabled'
    _audit(
        record,
        'resolver.production_readiness.validated',
        actor_user_id,
        {
            'ready': assessment.ready,
            'failed_checks': list(assessment.failed_checks),
            'evidence_hash': assessment.evidence_hash,
        },
    )
    db.session.flush()
    return record


def advance_rollout_stage(
    record: ResolverProductionReadinessRecord,
    *,
    target_stage: str,
    actor_user_id: int | None,
) -> ResolverProductionReadinessRecord:
    if target_stage not in STAGE_ORDER:
        raise ProductionReadinessError(f'Unknown rollout stage: {target_stage}.')
    current_index = STAGE_ORDER.index(record.rollout_stage)
    target_index = STAGE_ORDER.index(target_stage)
    if target_index > current_index + 1:
        raise ProductionReadinessError('Rollout stages must advance one step at a time.')
    if target_stage != 'disabled' and not record.evidence_hash:
        raise ProductionReadinessError('Readiness evidence must be recorded before rollout.')
    assessment = assess_readiness(results=record.validation_results_json, rollout_stage=record.rollout_stage)
    if target_stage in {'canary', 'production'} and not assessment.ready:
        raise ProductionReadinessError(
            'Production readiness checks are incomplete: ' + ', '.join(assessment.failed_checks)
        )
    policy = ResolverDeploymentPolicy.query.filter_by(
        cluster_id=record.cluster_id,
        action_key=record.action_key,
    ).one_or_none()
    if target_stage != 'disabled' and (policy is None or policy.lifecycle_status != 'active'):
        raise ProductionReadinessError('Resolver deployment policy must be active before rollout.')
    if target_stage == 'production':
        control = ResolverOperationalControl.query.filter_by(cluster_id=None).one_or_none()
        if control is None:
            raise ProductionReadinessError('Global resolver operational control must exist before production rollout.')
        record.approved_at = datetime.now(UTC)
        record.approved_by_user_id = actor_user_id
    elif target_stage == 'disabled':
        record.approved_at = None
        record.approved_by_user_id = None
    record.rollout_stage = target_stage
    _audit(
        record,
        'resolver.rollout_stage.changed',
        actor_user_id,
        {
            'previous_stage': STAGE_ORDER[current_index],
            'target_stage': target_stage,
            'evidence_hash': record.evidence_hash,
        },
    )
    db.session.flush()
    return record


def assert_production_execution_ready(
    *,
    cluster_id: str,
    action_key: str,
    cluster_environment: str | None = None,
) -> ResolverProductionReadinessRecord:
    record = ResolverProductionReadinessRecord.query.filter_by(
        cluster_id=cluster_id,
        action_key=action_key,
    ).one_or_none()
    if record is None or record.rollout_stage not in {'non_production', 'canary', 'production'}:
        raise ProductionReadinessError('Resolver action has not reached an executable rollout stage.')
    normalized_environment = str(cluster_environment or '').strip().lower().replace('-', '_').replace(' ', '_')
    if record.rollout_stage == 'non_production' and normalized_environment == 'production':
        raise ProductionReadinessError('Non-production rollout stage cannot execute against a production cluster.')
    assessment = assess_readiness(results=record.validation_results_json, rollout_stage=record.rollout_stage)
    if record.rollout_stage in {'canary', 'production'} and not assessment.ready:
        raise ProductionReadinessError('Resolver production readiness evidence is no longer valid.')
    if record.evidence_hash != assessment.evidence_hash:
        raise ProductionReadinessError('Resolver readiness evidence hash does not match stored validation results.')
    return record


def _audit(
    record: ResolverProductionReadinessRecord,
    action: str,
    actor_user_id: int | None,
    metadata: dict[str, object],
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'resolver_production_readiness'
    event.target_id = f'{record.cluster_id}:{record.action_key}'
    event.action = action
    event.summary = 'KAORI resolver controlled rollout state changed.'
    event.metadata_json = metadata
    db.session.add(event)
