from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.integrations.kubernetes.resolver_adapter import (
    KubernetesDeploymentRestartAdapter,
    NamespaceGuardrail,
)
from app.resolver.contracts import ResolverContext, ResolverError, ResolverResultStatus


class FakeGateway:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.dry_run_calls = 0
        self.execute_calls = 0
        self.state = {
            'name': 'api',
            'namespace': 'payments',
            'uid': 'uid-1',
            'resource_version': '41',
            'generation': 8,
            'observed_generation': 8,
            'annotations': {},
        }

    def can_patch_deployments(self, namespace: str) -> bool:
        return self.allowed

    def read_deployment(self, namespace: str, name: str):
        return dict(self.state)

    def patch_deployment(self, namespace: str, name: str, patch, *, dry_run: bool):
        if dry_run:
            self.dry_run_calls += 1
            return dict(self.state)
        self.execute_calls += 1
        self.state['resource_version'] = '42'
        self.state['generation'] = 9
        self.state['annotations'].update(patch['spec']['template']['metadata']['annotations'])
        return dict(self.state)


def context(**parameters):
    return ResolverContext(
        decision_id='dec-1',
        journal_id='journal-1',
        action_key='kubernetes.deployment.restart',
        evidence_hash='evidence',
        idempotency_key='idem',
        cluster_id='cluster-1',
        namespace='payments',
        parameters={'deployment_name': 'api', **parameters},
    )


def test_dry_run_precedes_mutation_and_execution_verifies_post_condition():
    gateway = FakeGateway()
    adapter = KubernetesDeploymentRestartAdapter(
        gateway_factory=lambda cluster_id: gateway,
        namespace_guardrail=NamespaceGuardrail(frozenset({'payments'})),
        clock=lambda: datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
    )

    dry_run = adapter.dry_run(context(resource_version='41'))
    assert dry_run.allowed is True
    assert gateway.dry_run_calls == 1
    assert gateway.execute_calls == 0
    assert dry_run.planned_changes[0]['precondition_resource_version'] == '41'
    assert dry_run.rollback_plan['snapshot_hash']

    result = adapter.execute(context(resource_version='41'), dry_run)
    assert result.status is ResolverResultStatus.SUCCEEDED
    assert gateway.execute_calls == 1
    assert result.rollback_reference.startswith('kubernetes-snapshot:')
    assert result.result['post_condition'] == 'restart annotation verified'


def test_resource_version_change_after_dry_run_fails_closed():
    gateway = FakeGateway()
    adapter = KubernetesDeploymentRestartAdapter(gateway_factory=lambda cluster_id: gateway)
    dry_run = adapter.dry_run(context())
    gateway.state['resource_version'] = '99'

    with pytest.raises(ResolverError, match='resourceVersion changed after dry-run'):
        adapter.execute(context(), dry_run)
    assert gateway.execute_calls == 0


def test_namespace_and_service_account_guardrails_block_before_mutation():
    gateway = FakeGateway(allowed=False)
    adapter = KubernetesDeploymentRestartAdapter(
        gateway_factory=lambda cluster_id: gateway,
        namespace_guardrail=NamespaceGuardrail(frozenset({'payments'})),
    )
    blocked = adapter.dry_run(context())
    assert blocked.allowed is False
    assert gateway.dry_run_calls == 0

    protected = KubernetesDeploymentRestartAdapter(gateway_factory=lambda cluster_id: gateway)
    protected_context = context()
    object.__setattr__(protected_context, 'namespace', 'kube-system')
    with pytest.raises(ResolverError, match='protected'):
        protected.dry_run(protected_context)
