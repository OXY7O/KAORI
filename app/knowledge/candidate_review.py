from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Collection, Mapping

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.intelligence.decision import PolicyOutcome, compute_evidence_hash, create_decision_snapshot
from app.intelligence.workflow import persist_decision
from app.models.audit import AuditEvent
from app.models.intelligence import IntelligenceDecision, IntelligenceDecisionCandidate
from app.models.knowledge import KnowledgeRunbookAlertBinding, KnowledgeRunbookRevision
from app.knowledge.matching import DecisionCandidate

CREATE_PERMISSION = 'intelligence.decisions.create'
VIEW_PERMISSION = 'intelligence.decisions.view'


class CandidateWorkflowError(RuntimeError):
    """Raised when candidate persistence or promotion violates review boundaries."""


def persist_candidate(
    candidate: DecisionCandidate,
    *,
    severity: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    ttl: timedelta = timedelta(minutes=30),
    now: datetime | None = None,
) -> IntelligenceDecisionCandidate:
    _require(actor_permissions, VIEW_PERMISSION)
    if candidate.executable:
        raise CandidateWorkflowError('Executable payloads cannot enter the candidate review workflow.')
    created_at = now or datetime.now(UTC)
    if ttl <= timedelta(0):
        raise CandidateWorkflowError('Candidate TTL must be positive.')

    binding = KnowledgeRunbookAlertBinding.query.filter_by(binding_key=candidate.binding_key).first()
    revision = KnowledgeRunbookRevision.query.filter_by(public_id=candidate.runbook_revision_id).first()
    if binding is None or revision is None or binding.runbook_revision_id != revision.id:
        raise CandidateWorkflowError('Candidate binding and runbook revision are no longer consistent.')
    _assert_revision_current(candidate, revision)

    evidence = dict(candidate.evidence)
    evidence_hash = compute_evidence_hash(evidence)
    deduplication_key = _deduplication_key(candidate, evidence_hash)
    existing = IntelligenceDecisionCandidate.query.filter_by(deduplication_key=deduplication_key).first()
    if existing is not None:
        return existing

    payload = _candidate_payload(candidate, evidence, severity)
    record = IntelligenceDecisionCandidate()
    record.binding_id = binding.id
    record.runbook_revision_id = revision.id
    record.deduplication_key = deduplication_key
    record.rule_key = candidate.rule_key
    record.alert_fingerprint = candidate.alert_fingerprint
    record.cluster_id = candidate.cluster_id
    record.namespace = candidate.namespace
    record.severity = (severity or 'info').strip().lower()
    record.evidence_json = evidence
    record.evidence_hash = evidence_hash
    record.candidate_json = payload
    record.review_status = 'pending'
    record.created_by_user_id = actor_user_id
    record.created_at = created_at
    record.expires_at = created_at + ttl
    db.session.add(record)
    _audit(actor_user_id, 'intelligence.candidate.created', record.public_id, {
        'binding_key': candidate.binding_key,
        'evidence_hash': evidence_hash,
        'executable': False,
    })
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = IntelligenceDecisionCandidate.query.filter_by(deduplication_key=deduplication_key).first()
        if existing is not None:
            return existing
        raise
    return record


def promote_candidate(
    record: IntelligenceDecisionCandidate,
    *,
    rule_version: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    reason: str | None = None,
    now: datetime | None = None,
    decision_ttl: timedelta = timedelta(minutes=15),
    maintenance_mode: bool = False,
    actor_can_execute: bool = False,
    blocked_actions: frozenset[str] = frozenset(),
) -> IntelligenceDecision:
    _require(actor_permissions, CREATE_PERMISSION)
    checked_at = now or datetime.now(UTC)
    _assert_pending(record, checked_at)
    revision = db.session.get(KnowledgeRunbookRevision, record.runbook_revision_id)
    binding = db.session.get(KnowledgeRunbookAlertBinding, record.binding_id)
    if revision is None or binding is None:
        raise CandidateWorkflowError('Candidate source binding or revision no longer exists.')
    candidate = record.candidate_json
    _assert_revision_current_payload(candidate, revision)
    if binding.lifecycle_status != 'active' or binding.runbook_revision_id != revision.id:
        raise CandidateWorkflowError('Candidate binding is no longer active or revision-consistent.')
    if compute_evidence_hash(record.evidence_json) != record.evidence_hash:
        raise CandidateWorkflowError('Candidate evidence changed after review creation.')

    finding = {
        'rule_key': candidate['rule_key'],
        'severity': record.severity,
        'evidence': record.evidence_json,
    }
    snapshot = create_decision_snapshot(
        finding,
        action_key=revision.action_key,
        rule_version=rule_version,
        knowledge_version=revision.version,
        runbook_key=revision.runbook.runbook_key,
        runbook_revision_id=revision.public_id,
        runbook_version=revision.version,
        runbook_content_hash=revision.content_hash,
        ttl=decision_ttl,
        now=checked_at,
        maintenance_mode=maintenance_mode,
        actor_can_execute=actor_can_execute,
        blocked_actions=blocked_actions,
    )
    _assert_policy_consistent(revision.approval_policy, snapshot.policy.outcome)
    decision = persist_decision(snapshot, actor_user_id=actor_user_id, actor_permissions=actor_permissions)
    record.review_status = 'promoted'
    record.reviewed_by_user_id = actor_user_id
    record.review_reason = reason.strip() if reason else None
    record.reviewed_at = checked_at
    record.promoted_decision_id = decision.id
    _audit(actor_user_id, 'intelligence.candidate.promoted', record.public_id, {
        'decision_public_id': decision.public_id,
        'runbook_content_hash': revision.content_hash,
    })
    db.session.commit()
    return decision


def dismiss_candidate(
    record: IntelligenceDecisionCandidate,
    *,
    reason: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    now: datetime | None = None,
) -> IntelligenceDecisionCandidate:
    _require(actor_permissions, CREATE_PERMISSION)
    if not reason.strip():
        raise CandidateWorkflowError('Candidate dismissal requires a reason.')
    checked_at = now or datetime.now(UTC)
    _assert_pending(record, checked_at)
    record.review_status = 'dismissed'
    record.review_reason = reason.strip()
    record.reviewed_by_user_id = actor_user_id
    record.reviewed_at = checked_at
    _audit(actor_user_id, 'intelligence.candidate.dismissed', record.public_id, {'reason': record.review_reason})
    db.session.commit()
    return record


def expire_stale_candidates(*, now: datetime | None = None) -> int:
    checked_at = now or datetime.now(UTC)
    rows = IntelligenceDecisionCandidate.query.filter(
        IntelligenceDecisionCandidate.review_status == 'pending',
        IntelligenceDecisionCandidate.expires_at <= checked_at,
    ).all()
    for row in rows:
        row.review_status = 'expired'
        row.reviewed_at = checked_at
    db.session.commit()
    return len(rows)


def _assert_pending(record: IntelligenceDecisionCandidate, now: datetime) -> None:
    if record.review_status != 'pending':
        raise CandidateWorkflowError(f'Candidate cannot be reviewed from {record.review_status}.')
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        record.review_status = 'expired'
        db.session.commit()
        raise CandidateWorkflowError('Candidate expired before review completion.')


def _assert_revision_current(candidate: DecisionCandidate, revision: KnowledgeRunbookRevision) -> None:
    _assert_revision_current_payload(_candidate_payload(candidate, dict(candidate.evidence), 'info'), revision)


def _assert_revision_current_payload(candidate: Mapping[str, Any], revision: KnowledgeRunbookRevision) -> None:
    if revision.publication_status != 'published':
        raise CandidateWorkflowError('Candidate requires a currently published runbook revision.')
    if candidate['runbook_revision_id'] != revision.public_id or candidate['runbook_content_hash'] != revision.content_hash:
        raise CandidateWorkflowError('Candidate runbook revision changed after matching.')
    if candidate['action_key'] != revision.action_key or candidate['resolver_key'] != revision.resolver_key:
        raise CandidateWorkflowError('Candidate action or resolver no longer matches the runbook revision.')


def _assert_policy_consistent(runbook_policy: str, outcome: PolicyOutcome) -> None:
    rank = {'allowed': 0, 'needs_approval': 1, 'blocked': 2}
    if rank[outcome.value] < rank[runbook_policy]:
        raise CandidateWorkflowError('Decision policy is weaker than the locked runbook approval policy.')
    if outcome is PolicyOutcome.BLOCKED:
        raise CandidateWorkflowError('Blocked candidates cannot be promoted into decisions.')


def _deduplication_key(candidate: DecisionCandidate, evidence_hash: str) -> str:
    payload = {
        'binding_key': candidate.binding_key,
        'alert_fingerprint': candidate.alert_fingerprint,
        'runbook_revision_id': candidate.runbook_revision_id,
        'evidence_hash': evidence_hash,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _candidate_payload(candidate: DecisionCandidate, evidence: Mapping[str, Any], severity: str) -> dict[str, Any]:
    return {
        'binding_key': candidate.binding_key,
        'runbook_key': candidate.runbook_key,
        'runbook_revision_id': candidate.runbook_revision_id,
        'runbook_version': candidate.runbook_version,
        'runbook_content_hash': candidate.runbook_content_hash,
        'action_key': candidate.action_key,
        'resolver_key': candidate.resolver_key,
        'approval_policy': candidate.approval_policy,
        'rule_key': candidate.rule_key,
        'alert_fingerprint': candidate.alert_fingerprint,
        'cluster_id': candidate.cluster_id,
        'namespace': candidate.namespace,
        'severity': severity,
        'evidence': dict(evidence),
        'executable': False,
    }


def _require(permissions: Collection[str], permission: str) -> None:
    if permission not in permissions:
        raise CandidateWorkflowError(f'Missing required permission: {permission}.')


def _audit(actor_user_id: int | None, action: str, target_id: str, metadata: Mapping[str, Any]) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.action = action
    event.target_type = 'intelligence_decision_candidate'
    event.target_id = target_id
    event.summary = action.replace('.', ' ')
    event.metadata_json = dict(metadata)
    db.session.add(event)
