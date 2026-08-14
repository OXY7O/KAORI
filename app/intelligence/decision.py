from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class DecisionError(ValueError):
    """Raised when a decision or execution authorization is invalid."""


class PolicyOutcome(StrEnum):
    ALLOWED = 'allowed'
    NEEDS_APPROVAL = 'needs_approval'
    BLOCKED = 'blocked'


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    outcome: PolicyOutcome
    reason: str
    approval_required: bool


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    decision_id: str
    recommendation_key: str
    rule_key: str
    rule_version: str
    knowledge_version: str | None
    action_key: str
    cluster_id: str | None
    namespace: str | None
    severity: str
    evidence: Mapping[str, Any]
    evidence_hash: str
    inventory_generation: str | None
    alert_fingerprint: str | None
    policy: DecisionPolicy
    created_at: datetime
    expires_at: datetime
    runbook_key: str | None = None
    runbook_revision_id: str | None = None
    runbook_version: str | None = None
    runbook_content_hash: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            'decision_id': self.decision_id,
            'recommendation_key': self.recommendation_key,
            'rule_key': self.rule_key,
            'rule_version': self.rule_version,
            'knowledge_version': self.knowledge_version,
            'runbook_key': self.runbook_key,
            'runbook_revision_id': self.runbook_revision_id,
            'runbook_version': self.runbook_version,
            'runbook_content_hash': self.runbook_content_hash,
            'action_key': self.action_key,
            'cluster_id': self.cluster_id,
            'namespace': self.namespace,
            'severity': self.severity,
            'evidence': _thaw(self.evidence),
            'evidence_hash': self.evidence_hash,
            'inventory_generation': self.inventory_generation,
            'alert_fingerprint': self.alert_fingerprint,
            'policy': {
                'outcome': self.policy.outcome.value,
                'reason': self.policy.reason,
                'approval_required': self.policy.approval_required,
            },
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    decision_id: str
    action_key: str
    evidence_hash: str
    issued_at: datetime
    expires_at: datetime
    nonce: str


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        default=str,
    ).encode('utf-8')


def compute_evidence_hash(evidence: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(dict(evidence))).hexdigest()


def evaluate_policy(
    *,
    severity: str,
    action_key: str,
    blocked_actions: frozenset[str] = frozenset(),
    minimum_outcome: PolicyOutcome = PolicyOutcome.ALLOWED,
) -> DecisionPolicy:
    normalized_severity = (severity or 'info').strip().lower()
    normalized_action = action_key.strip()

    if not normalized_action:
        return DecisionPolicy(PolicyOutcome.BLOCKED, 'Decision has no executable action.', False)
    if normalized_action in blocked_actions:
        return DecisionPolicy(PolicyOutcome.BLOCKED, 'Action is blocked by operational policy.', False)
    severity_outcome = (
        PolicyOutcome.NEEDS_APPROVAL
        if normalized_severity in {'critical', 'warning'}
        else PolicyOutcome.ALLOWED
    )
    rank = {PolicyOutcome.ALLOWED: 0, PolicyOutcome.NEEDS_APPROVAL: 1, PolicyOutcome.BLOCKED: 2}
    outcome = minimum_outcome if rank[minimum_outcome] > rank[severity_outcome] else severity_outcome
    if outcome is PolicyOutcome.BLOCKED:
        return DecisionPolicy(PolicyOutcome.BLOCKED, 'Runbook policy blocks execution.', False)
    if outcome is PolicyOutcome.NEEDS_APPROVAL:
        reason = (
            f'{normalized_severity.title()} remediation requires explicit approval.'
            if severity_outcome is PolicyOutcome.NEEDS_APPROVAL
            else 'Published runbook policy requires explicit approval.'
        )
        return DecisionPolicy(PolicyOutcome.NEEDS_APPROVAL, reason, True)
    return DecisionPolicy(PolicyOutcome.ALLOWED, 'Published policy allows execution without additional approval.', False)


def create_decision_snapshot(
    finding: Mapping[str, Any],
    *,
    action_key: str,
    rule_version: str,
    knowledge_version: str | None = None,
    runbook_key: str | None = None,
    runbook_revision_id: str | None = None,
    runbook_version: str | None = None,
    runbook_content_hash: str | None = None,
    ttl: timedelta = timedelta(minutes=15),
    now: datetime | None = None,
    blocked_actions: frozenset[str] = frozenset(),
    minimum_outcome: PolicyOutcome = PolicyOutcome.ALLOWED,
) -> DecisionSnapshot:
    created_at = now or datetime.now(UTC)
    if created_at.tzinfo is None:
        raise DecisionError('Decision timestamps must be timezone-aware.')
    if ttl <= timedelta(0):
        raise DecisionError('Decision TTL must be positive.')

    evidence = finding.get('evidence')
    if not isinstance(evidence, Mapping):
        raise DecisionError('Recommendation finding must contain mapping evidence.')

    recommendation_key = str(finding.get('rule_key') or '').strip()
    base_rule_key = recommendation_key.split(':', 1)[0]
    if not recommendation_key or not base_rule_key:
        raise DecisionError('Recommendation finding must contain a rule key.')

    evidence_copy = json.loads(_canonical_json(dict(evidence)).decode('utf-8'))
    frozen_evidence = _freeze(evidence_copy)
    severity = str(finding.get('severity') or 'info').strip().lower()
    policy = evaluate_policy(
        severity=severity,
        action_key=action_key,
        blocked_actions=blocked_actions,
        minimum_outcome=minimum_outcome,
    )

    return DecisionSnapshot(
        decision_id=secrets.token_urlsafe(18),
        recommendation_key=recommendation_key,
        rule_key=base_rule_key,
        rule_version=rule_version,
        knowledge_version=knowledge_version,
        runbook_key=runbook_key,
        runbook_revision_id=runbook_revision_id,
        runbook_version=runbook_version,
        runbook_content_hash=runbook_content_hash,
        action_key=action_key,
        cluster_id=_optional_text(evidence_copy.get('cluster_id')),
        namespace=_optional_text(evidence_copy.get('namespace')),
        severity=severity,
        evidence=frozen_evidence,
        evidence_hash=compute_evidence_hash(evidence_copy),
        inventory_generation=_optional_text(evidence_copy.get('inventory_generation')),
        alert_fingerprint=_optional_text(evidence_copy.get('alert_fingerprint')),
        policy=policy,
        created_at=created_at,
        expires_at=created_at + ttl,
    )


def issue_execution_token(
    decision: DecisionSnapshot,
    *,
    secret_key: str,
    approved: bool = False,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    _assert_decision_executable(decision, approved=approved, now=issued_at)
    if not secret_key:
        raise DecisionError('Execution token secret key is required.')

    authorization = ExecutionAuthorization(
        decision_id=decision.decision_id,
        action_key=decision.action_key,
        evidence_hash=decision.evidence_hash,
        issued_at=issued_at,
        expires_at=decision.expires_at,
        nonce=secrets.token_urlsafe(12),
    )
    payload = {
        **asdict(authorization),
        'issued_at': authorization.issued_at.isoformat(),
        'expires_at': authorization.expires_at.isoformat(),
    }
    encoded = _canonical_json(payload).hex()
    signature = hmac.new(secret_key.encode('utf-8'), encoded.encode('ascii'), hashlib.sha256).hexdigest()
    return f'{encoded}.{signature}'


def authorize_execution(
    decision: DecisionSnapshot,
    token: str,
    *,
    secret_key: str,
    current_evidence: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> ExecutionAuthorization:
    checked_at = now or datetime.now(UTC)
    if not isinstance(decision, DecisionSnapshot):
        raise DecisionError('Executor requires a DecisionSnapshot, not a recommendation payload.')
    try:
        encoded, supplied_signature = token.split('.', 1)
    except ValueError as exc:
        raise DecisionError('Malformed execution token.') from exc

    expected_signature = hmac.new(secret_key.encode('utf-8'), encoded.encode('ascii'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise DecisionError('Invalid execution token signature.')

    try:
        payload = json.loads(bytes.fromhex(encoded).decode('utf-8'))
        authorization = ExecutionAuthorization(
            decision_id=str(payload['decision_id']),
            action_key=str(payload['action_key']),
            evidence_hash=str(payload['evidence_hash']),
            issued_at=datetime.fromisoformat(payload['issued_at']),
            expires_at=datetime.fromisoformat(payload['expires_at']),
            nonce=str(payload['nonce']),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DecisionError('Invalid execution token payload.') from exc

    if checked_at.tzinfo is None:
        raise DecisionError('Execution validation timestamp must be timezone-aware.')
    if checked_at >= authorization.expires_at or checked_at >= decision.expires_at:
        raise DecisionError('Execution token or decision has expired.')
    if authorization.decision_id != decision.decision_id:
        raise DecisionError('Execution token does not belong to this decision.')
    if authorization.action_key != decision.action_key:
        raise DecisionError('Execution token action does not match the decision.')
    if authorization.evidence_hash != decision.evidence_hash:
        raise DecisionError('Execution token evidence does not match the decision.')
    if current_evidence is not None and compute_evidence_hash(current_evidence) != decision.evidence_hash:
        raise DecisionError('Current evidence differs from the approved decision snapshot.')

    return authorization


def _assert_decision_executable(
    decision: DecisionSnapshot,
    *,
    approved: bool,
    now: datetime,
) -> None:
    if now.tzinfo is None:
        raise DecisionError('Execution token timestamp must be timezone-aware.')
    if now >= decision.expires_at:
        raise DecisionError('Decision has expired.')
    if decision.policy.outcome is PolicyOutcome.BLOCKED:
        raise DecisionError(decision.policy.reason)
    if decision.policy.approval_required and not approved:
        raise DecisionError('Decision requires explicit approval before token issuance.')


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _optional_text(value: Any) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None
