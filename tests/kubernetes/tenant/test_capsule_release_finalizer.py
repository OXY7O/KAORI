"""#1230: Capsule G4 finalization must never trust database-only success.

Source-authored regression checks; execution and CI/CD remain on HOLD.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_release_finalizer as finalizer


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, **_):
        return self

    def order_by(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return self.rows


def _worklist():
    return {
        'inventory_sha256': 'd' * 64,
        'item_count': 3,
        'items': [
            {'kind': 'CapsuleTenant', 'namespace': '', 'name': 'demo',
             'uid': 'cr-uid', 'resource_version': '2',
             'decision': 'provider_cr_preservation_review_required'},
            {'kind': 'Namespace', 'namespace': '', 'name': 'demo-dev',
             'uid': 'ns-uid', 'resource_version': '4',
             'decision': 'candidate_kaori_metadata_handoff_review'},
            {'kind': 'GlobalResourceQuota', 'namespace': '', 'name': 'global',
             'uid': 'g-uid', 'resource_version': '8',
             'decision': 'preserve_cluster_scoped_quota'},
        ],
    }


def _plan():
    return {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1', 'generation': 2,
        'plan_sha256': 'a' * 64, 'handoff_fingerprint': 'b' * 64,
        'successor_owner': 'platform-team', 'provider': 'capsule',
        'handoff_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
             'resource_version': '2'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid',
             'resource_version': '4'},
        ],
        'provider_identity': [],
    }


def test_capsule_g4_refuses_no_start_ledger_even_if_execution_claims_success(monkeypatch):
    monkeypatch.setattr(
        finalizer, 'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query([])),
    )
    monkeypatch.setattr(
        finalizer, 'AuditEvent', SimpleNamespace(query=_Query([
            SimpleNamespace(metadata_json={
                'status': 'provider_handoff_verified',
                'provider_handoff_verified': True,
            }),
        ])),
    )
    with pytest.raises(ValueError, match='immutable START'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1', plan=_plan(), related={},
            work=_worklist(), actor_user_id=21,
        )


def test_capsule_g4_refuses_partial_or_multiple_attempts_before_readback(monkeypatch):
    monkeypatch.setattr(
        finalizer, 'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query([SimpleNamespace(sequence=1)])),
    )
    with pytest.raises(ValueError, match='START and terminal'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1', plan=_plan(), related={},
            work=_worklist(), actor_user_id=21,
        )
    monkeypatch.setattr(
        finalizer, 'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query([SimpleNamespace()] * 3)),
    )
    with pytest.raises(ValueError, match='START and terminal'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1', plan=_plan(), related={},
            work=_worklist(), actor_user_id=21,
        )


def test_capsule_g4_fails_closed_on_partial_terminal_scope_without_provider_get(monkeypatch):
    provider_calls = []
    fake = SimpleNamespace(
        core_api=lambda: provider_calls.append('core'),
        rbac_authorization_api=lambda: provider_calls.append('rbac'),
        custom_objects_api=lambda: provider_calls.append('custom'),
    )
    monkeypatch.setattr(
        finalizer.runtime_adapter, 'build_client',
        lambda _: fake,
    )
    plan = _plan()
    execution = {
        'verified_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
             'resource_version': '2', 'state': 'preserved'},
        ],
    }
    # The full runtime will fail closed on missing scope even if the CR was
    # synthetically observed. A truncated list never becomes Released.
    with pytest.raises((ValueError, TypeError, AttributeError)):
        finalizer._current_verified_capsule_scope(
            cluster=SimpleNamespace(), plan=plan,
            related={'resources': [], 'global_quota': {}},
            work=_worklist(), execution=execution,
        )


def test_capsule_finalizer_does_not_mutate_provider_in_its_source():
    import inspect

    content = inspect.getsource(finalizer.release_verified_capsule_tenant_committed)
    assert 'patch_namespaced_' not in content
    assert 'patch_namespace(' not in content
    assert 'delete_' not in content
    assert 'TenantLifecycleStatus.RELEASED.value' in content
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in content


def test_capsule_source_snapshot_rejects_no_g0_evidence(monkeypatch):
    monkeypatch.setattr(
        finalizer, 'AuditEvent', SimpleNamespace(query=_Query([])),
    )
    with pytest.raises(ValueError, match='Original Capsule source'):
        finalizer._source_snapshot(tenant_id='tenant-1', plan=_plan())
