from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.resolver import (
    DryRunResult,
    ResolverContext,
    ResolverError,
    ResolverRegistry,
    ResolverResult,
    ResolverResultStatus,
    build_idempotency_key,
)


@dataclass
class FakeAdapter:
    action_key: str = 'kubernetes.workload.restart'

    def dry_run(self, context: ResolverContext) -> DryRunResult:
        return DryRunResult(
            allowed=True,
            summary='Restart can be applied safely.',
            planned_changes=({'resource': 'deployment/api', 'operation': 'restart'},),
            rollback_plan={'strategy': 'observe-rollout'},
        )

    def execute(self, context: ResolverContext, dry_run: DryRunResult) -> ResolverResult:
        return ResolverResult(
            status=ResolverResultStatus.SUCCEEDED,
            summary='Restart dispatched.',
            result={'idempotency_key': context.idempotency_key},
        )


def test_registry_fails_closed_for_unknown_and_duplicate_actions() -> None:
    registry = ResolverRegistry()
    registry.register(FakeAdapter())

    assert registry.resolve('kubernetes.workload.restart').action_key == 'kubernetes.workload.restart'
    with pytest.raises(ResolverError, match='No resolver adapter'):
        registry.resolve('kubernetes.secret.delete')
    with pytest.raises(ResolverError, match='already registered'):
        registry.register(FakeAdapter())


def test_idempotency_key_is_bound_to_decision_action_and_evidence() -> None:
    first = build_idempotency_key(decision_id='decision-1', action_key='restart', evidence_hash='a' * 64)
    repeated = build_idempotency_key(decision_id='decision-1', action_key='restart', evidence_hash='a' * 64)
    changed = build_idempotency_key(decision_id='decision-1', action_key='restart', evidence_hash='b' * 64)

    assert first == repeated
    assert first != changed
    assert len(first) == 64


def test_resolver_context_parameters_are_read_only() -> None:
    context = ResolverContext(
        decision_id='decision-1',
        journal_id='journal-1',
        action_key='restart',
        evidence_hash='a' * 64,
        idempotency_key='b' * 64,
        cluster_id='cluster-1',
        namespace='default',
        parameters={'replicas': 2},
    )

    with pytest.raises(TypeError):
        context.parameters['replicas'] = 3  # type: ignore[index]
