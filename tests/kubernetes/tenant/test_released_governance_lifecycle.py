from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.release_preflight import _release_blockers, release_adopted_tenant_committed


def _tenant(*, mutated: object = False):
    return SimpleNamespace(
        ownership_status='adopted',
        lifecycle_status='ready',
        provider_key='native_kubernetes',
        provider_state='native',
        reconciliation_authority='native_kubernetes',
        provider_evidence_json={'provider_mutation_performed': mutated},
    )


def _namespace(*, allocation: bool = False, status: str = 'ready'):
    return SimpleNamespace(
        namespace='sandbox',
        ownership_status='adopted',
        provisioning_status=status,
        resource_profile_id=1 if allocation else None,
    )


def test_release_blocks_adoption_with_provider_mutation_or_unproven_handoff():
    counts = {'Access Grants': 0, 'credentials': 0, 'Memberships': 0}
    assert _release_blockers(_tenant(mutated=True), [_namespace()], counts=counts)
    assert _release_blockers(_tenant(mutated=None), [_namespace()], counts=counts)
    assert _release_blockers(_tenant(mutated=False), [_namespace(allocation=True)], counts=counts)
    assert _release_blockers(_tenant(mutated=False), [_namespace(status='failed')], counts=counts)
    assert _release_blockers(_tenant(mutated=False), [_namespace()], counts=counts) == []


def test_release_requires_explicit_approval_and_prior_eligible_preflight(monkeypatch):
    with pytest.raises(ValueError, match='approval'):
        release_adopted_tenant_committed(tenant_id='sandbox', actor_user_id=1, approved=False)

    monkeypatch.setattr(
        'app.kubernetes.tenant.release_preflight.latest_tenant_release_preflight',
        lambda _: None,
    )
    with pytest.raises(ValueError, match='preflight'):
        release_adopted_tenant_committed(tenant_id='sandbox', actor_user_id=1, approved=True)


def test_release_stale_preflight_is_rejected_before_provider_reads(monkeypatch):
    monkeypatch.setattr(
        'app.kubernetes.tenant.release_preflight.latest_tenant_release_preflight',
        lambda _: {
            'status': 'handoff_review_required',
            'checked_at': '2020-01-01T00:00:00+00:00',
        },
    )
    with pytest.raises(ValueError, match='stale'):
        release_adopted_tenant_committed(tenant_id='sandbox', actor_user_id=1, approved=True)


def test_released_model_statuses_are_distinct_from_decommissioned():
    from app.models.tenant import TenantLifecycleStatus, TenantNamespaceProvisioningStatus

    assert TenantLifecycleStatus.RELEASED.value == 'released'
    assert TenantLifecycleStatus.RELEASED != TenantLifecycleStatus.DECOMMISSIONED
    assert TenantNamespaceProvisioningStatus.RELEASED.value == 'released'
    assert TenantNamespaceProvisioningStatus.RELEASED != TenantNamespaceProvisioningStatus.DEPROVISIONED
