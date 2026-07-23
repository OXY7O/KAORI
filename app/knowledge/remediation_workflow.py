from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Collection, Mapping, Sequence

from app.intelligence.workflow import (
    approve_decision,
    issue_persisted_execution_token,
)
from app.knowledge.candidate_review import persist_candidate, promote_candidate
from app.knowledge.matching import match_alert_to_runbook
from app.models.intelligence import (
    IntelligenceDecision,
    IntelligenceDecisionCandidate,
    IntelligenceExecutionJournal,
)
from app.models.knowledge import KnowledgeRunbookAlertBinding
from app.resolver.orchestration import enqueue_execution_delivery


class RemediationWorkflowError(RuntimeError):
    """Raised when the end-to-end remediation workflow crosses a safety boundary."""


@dataclass(frozen=True, slots=True)
class CandidateIntakeResult:
    candidate: IntelligenceDecisionCandidate


@dataclass(frozen=True, slots=True)
class PromotionResult:
    candidate: IntelligenceDecisionCandidate
    decision: IntelligenceDecision


@dataclass(frozen=True, slots=True)
class DispatchResult:
    decision: IntelligenceDecision
    journal: IntelligenceExecutionJournal
    job: Any
    created: bool


def ingest_alert_for_review(
    alert: Mapping[str, Any],
    *,
    bindings: Sequence[KnowledgeRunbookAlertBinding],
    severity: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    ttl: timedelta = timedelta(minutes=30),
    now: datetime | None = None,
) -> CandidateIntakeResult:
    """Match an alert and persist one non-executable review candidate."""
    matched = match_alert_to_runbook(alert, bindings)
    if matched.executable:
        raise RemediationWorkflowError('Alert matching must never produce an executable candidate.')
    # persist_candidate performs the durable deduplication check; the database
    # uniqueness constraint remains authoritative under concurrent alert delivery.
    record = persist_candidate(
        matched,
        severity=severity,
        actor_user_id=actor_user_id,
        actor_permissions=actor_permissions,
        ttl=ttl,
        now=now,
    )
    return CandidateIntakeResult(candidate=record)


def promote_reviewed_candidate(
    candidate: IntelligenceDecisionCandidate,
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
) -> PromotionResult:
    """Explicitly promote a reviewed candidate into an immutable decision."""
    decision = promote_candidate(
        candidate,
        rule_version=rule_version,
        actor_user_id=actor_user_id,
        actor_permissions=actor_permissions,
        reason=reason,
        now=now,
        decision_ttl=decision_ttl,
        maintenance_mode=maintenance_mode,
        actor_can_execute=actor_can_execute,
        blocked_actions=blocked_actions,
    )
    return PromotionResult(candidate=candidate, decision=decision)


def approve_and_enqueue_decision(
    decision: IntelligenceDecision,
    *,
    task: Any,
    secret_key: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    approval_reason: str | None = None,
    now: datetime | None = None,
    max_attempts: int = 3,
) -> DispatchResult:
    """Approve when required, issue one-time authorization, then enqueue once."""
    if decision.workflow_status == 'pending_approval':
        approve_decision(
            decision,
            actor_user_id=actor_user_id,
            actor_permissions=actor_permissions,
            reason=approval_reason,
            now=now,
        )
    elif decision.workflow_status not in {'ready', 'approved'}:
        raise RemediationWorkflowError(
            f'Decision cannot enter execution delivery from {decision.workflow_status}.'
        )

    token, journal = issue_persisted_execution_token(
        decision,
        secret_key=secret_key,
        actor_user_id=actor_user_id,
        actor_permissions=actor_permissions,
        now=now,
    )
    job, created = enqueue_execution_delivery(
        journal,
        task=task,
        token=token,
        secret_key=secret_key,
        actor_user_id=actor_user_id,
        max_attempts=max_attempts,
    )
    return DispatchResult(decision=decision, journal=journal, job=job, created=created)
