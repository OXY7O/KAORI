from __future__ import annotations

from datetime import UTC, datetime
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
        provisioning_evidence_json={'provider_mutation_performed': False},
    )


def test_release_blocks_adoption_with_provider_mutation_or_unproven_handoff():
    counts = {'Access Grants': 0, 'credentials': 0, 'Memberships': 0}
    assert _release_blockers(_tenant(mutated=True), [_namespace()], counts=counts)
    assert _release_blockers(_tenant(mutated=None), [_namespace()], counts=counts)
    assert _release_blockers(_tenant(mutated=False), [_namespace(allocation=True)], counts=counts)
    record = _namespace()
    record.provisioning_evidence_json = {'provider_mutation_performed': True}
    assert _release_blockers(_tenant(mutated=False), [record], counts=counts)
    record.provisioning_evidence_json = {}
    assert _release_blockers(_tenant(mutated=False), [record], counts=counts)
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


def test_release_does_not_commit_when_provider_resource_version_changes(monkeypatch):
    from app.kubernetes.tenant import release_preflight

    timestamp = datetime.now(UTC).isoformat()
    shared = {
        'status': 'handoff_review_required',
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 1, 'provider': 'native_kubernetes',
        'ownership': 'adopted', 'checked_at': timestamp,
    }
    previous = {
        **shared,
        'live_provider_identity': [
            {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'ns-a', 'resource_version': '1'}
        ],
    }
    next_snapshot = {
        **shared, 'blockers': [],
        'live_provider_identity': [
            {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'ns-a', 'resource_version': '2'}
        ],
    }
    monkeypatch.setattr(release_preflight, 'latest_tenant_release_preflight', lambda _: previous)
    monkeypatch.setattr(
        release_preflight,
        'review_tenant_release_preflight_committed',
        lambda **_: next_snapshot,
    )

    with pytest.raises(ValueError, match='UID/resourceVersion changed'):
        release_adopted_tenant_committed(tenant_id='tenant-a', actor_user_id=1, approved=True)


def test_release_does_not_commit_after_preflight_blocks_new_dependencies(monkeypatch):
    from app.kubernetes.tenant import release_preflight

    timestamp = datetime.now(UTC).isoformat()
    snapshot = {
        'status': 'handoff_review_required',
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 1, 'provider': 'native_kubernetes',
        'ownership': 'adopted', 'checked_at': timestamp,
        'live_provider_identity': [
            {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'ns-a', 'resource_version': '1'}
        ],
    }
    monkeypatch.setattr(release_preflight, 'latest_tenant_release_preflight', lambda _: snapshot)
    monkeypatch.setattr(
        release_preflight,
        'review_tenant_release_preflight_committed',
        lambda **_: {**snapshot, 'blockers': ['new active Access Grant']},
    )
    with pytest.raises(ValueError, match='newly observed provider'):
        release_adopted_tenant_committed(tenant_id='tenant-a', actor_user_id=1, approved=True)


def test_release_detects_changed_handoff_inventory_even_when_namespace_uid_is_stable(monkeypatch):
    from app.kubernetes.tenant import release_preflight

    timestamp = datetime.now(UTC).isoformat()
    provider = [
        {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'uid',
         'resource_version': '12'}
    ]
    snapshot = {
        'status': 'handoff_review_required',
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 1, 'provider': 'native_kubernetes',
        'ownership': 'adopted', 'checked_at': timestamp,
        'live_provider_identity': provider,
        'handoff_components': [
            {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'uid',
             'resource_version': '12'}
        ],
        'handoff_fingerprint': 'old-fingerprint',
    }
    monkeypatch.setattr(release_preflight, 'latest_tenant_release_preflight', lambda _: snapshot)
    monkeypatch.setattr(
        release_preflight, 'review_tenant_release_preflight_committed',
        lambda **_: {**snapshot, 'blockers': [], 'handoff_fingerprint': 'new-fingerprint'},
    )
    with pytest.raises(ValueError, match='handoff evidence changed'):
        release_adopted_tenant_committed(tenant_id='tenant-a', actor_user_id=1, approved=True)
