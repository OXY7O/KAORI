from datetime import UTC, datetime, timedelta

import pytest

from app.intelligence.decision import (
    DecisionError,
    PolicyOutcome,
    authorize_execution,
    create_decision_snapshot,
    issue_execution_token,
)


def _finding() -> dict:
    return {
        'rule_key': 'kubernetes.pod.unhealthy_phase:cluster-a:payments:CrashLoopBackOff',
        'severity': 'critical',
        'evidence': {
            'cluster_id': 'cluster-a',
            'namespace': 'payments',
            'affected_count': 2,
            'phase': 'CrashLoopBackOff',
            'inventory_generation': '2026-07-23T10:00:00+00:00',
        },
    }


def test_decision_snapshot_is_immutable_and_requires_approval() -> None:
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    decision = create_decision_snapshot(
        _finding(),
        action_key='kubernetes.workload.restart',
        rule_version='2026.07.1',
        knowledge_version='runbook-12@v3',
        actor_can_execute=True,
        now=now,
    )

    assert decision.policy.outcome is PolicyOutcome.NEEDS_APPROVAL
    assert decision.evidence_hash
    assert decision.inventory_generation == '2026-07-23T10:00:00+00:00'
    with pytest.raises((AttributeError, TypeError)):
        decision.action_key = 'different.action'  # type: ignore[misc]
    with pytest.raises(TypeError):
        decision.evidence['affected_count'] = 99  # type: ignore[index]


def test_executor_rejects_recommendation_payload_and_changed_evidence() -> None:
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    decision = create_decision_snapshot(
        _finding(),
        action_key='kubernetes.workload.restart',
        rule_version='2026.07.1',
        actor_can_execute=True,
        now=now,
    )
    token = issue_execution_token(decision, secret_key='test-secret', approved=True, now=now)

    with pytest.raises(DecisionError, match='DecisionSnapshot'):
        authorize_execution(_finding(), token, secret_key='test-secret', now=now)  # type: ignore[arg-type]

    changed = dict(decision.evidence)
    changed['affected_count'] = 1
    with pytest.raises(DecisionError, match='Current evidence differs'):
        authorize_execution(
            decision,
            token,
            secret_key='test-secret',
            current_evidence=changed,
            now=now,
        )


def test_token_is_bound_to_decision_action_evidence_and_expiry() -> None:
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    decision = create_decision_snapshot(
        _finding(),
        action_key='kubernetes.workload.restart',
        rule_version='2026.07.1',
        actor_can_execute=True,
        ttl=timedelta(minutes=5),
        now=now,
    )
    token = issue_execution_token(decision, secret_key='test-secret', approved=True, now=now)
    authorization = authorize_execution(
        decision,
        token,
        secret_key='test-secret',
        current_evidence=decision.evidence,
        now=now + timedelta(minutes=1),
    )
    assert authorization.decision_id == decision.decision_id

    with pytest.raises(DecisionError, match='expired'):
        authorize_execution(
            decision,
            token,
            secret_key='test-secret',
            now=now + timedelta(minutes=5),
        )
