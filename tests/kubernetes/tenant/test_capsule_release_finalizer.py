"""#1230: Capsule G4 finalization must never trust database-only success.

Source-authored regression checks; execution and CI/CD remain on HOLD.
"""

from __future__ import annotations

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
            {
                'kind': 'CapsuleTenant',
                'namespace': '',
                'name': 'demo',
                'uid': 'cr-uid',
                'resource_version': '2',
                'decision': 'provider_cr_preservation_review_required',
            },
            {
                'kind': 'Namespace',
                'namespace': '',
                'name': 'demo-dev',
                'uid': 'ns-uid',
                'resource_version': '4',
                'decision': 'candidate_kaori_metadata_handoff_review',
            },
            {
                'kind': 'GlobalResourceQuota',
                'namespace': '',
                'name': 'global',
                'uid': 'g-uid',
                'resource_version': '8',
                'decision': 'preserve_cluster_scoped_quota',
            },
        ],
    }


def _plan():
    return {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 2,
        'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'b' * 64,
        'successor_owner': 'platform-team',
        'provider': 'capsule',
        'handoff_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '2'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '4'},
        ],
        'provider_identity': [],
    }


def test_capsule_g4_refuses_no_start_ledger_even_if_execution_claims_success(monkeypatch):
    monkeypatch.setattr(
        finalizer,
        'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query([])),
    )
    monkeypatch.setattr(
        finalizer,
        'AuditEvent',
        SimpleNamespace(
            query=_Query(
                [
                    SimpleNamespace(
                        metadata_json={
                            'status': 'provider_handoff_verified',
                            'provider_handoff_verified': True,
                        }
                    ),
                ]
            )
        ),
    )
    with pytest.raises(ValueError, match='immutable START'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1',
            plan=_plan(),
            related={},
            work=_worklist(),
            actor_user_id=21,
        )


def test_capsule_g4_refuses_partial_or_multiple_attempts_before_readback(monkeypatch):
    monkeypatch.setattr(
        finalizer,
        'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query([SimpleNamespace(sequence=1)])),
    )
    with pytest.raises(ValueError, match='START and terminal'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1',
            plan=_plan(),
            related={},
            work=_worklist(),
            actor_user_id=21,
        )
    monkeypatch.setattr(
        finalizer,
        'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query([SimpleNamespace()] * 3)),
    )
    with pytest.raises(ValueError, match='START and terminal'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1',
            plan=_plan(),
            related={},
            work=_worklist(),
            actor_user_id=21,
        )


def test_capsule_g4_fails_closed_on_partial_terminal_scope_without_provider_get(monkeypatch):
    provider_calls = []
    fake = SimpleNamespace(
        core_api=lambda: provider_calls.append('core'),
        rbac_authorization_api=lambda: provider_calls.append('rbac'),
        custom_objects_api=lambda: provider_calls.append('custom'),
    )
    monkeypatch.setattr(
        finalizer.runtime_adapter,
        'build_client',
        lambda _: fake,
    )
    plan = _plan()
    execution = {
        'verified_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '2', 'state': 'preserved'},
        ],
    }
    # The full runtime will fail closed on missing scope even if the CR was
    # synthetically observed. A truncated list never becomes Released.
    with pytest.raises((ValueError, TypeError, AttributeError)):
        finalizer._current_verified_capsule_scope(
            cluster=SimpleNamespace(),
            plan=plan,
            related={'resources': [], 'global_quota': {}},
            work=_worklist(),
            execution=execution,
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
        finalizer,
        'AuditEvent',
        SimpleNamespace(query=_Query([])),
    )
    with pytest.raises(ValueError, match='Original Capsule source'):
        finalizer._source_snapshot(tenant_id='tenant-1', plan=_plan())


def _ledger_and_g3_receipt():
    from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum
    from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest

    plan = _plan()
    work = _worklist()
    start = {
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'actor_user_id': 21,
        'worklist_sha256': work['inventory_sha256'],
        'event_type': 'started',
    }
    start['event_sha256'] = _event_checksum(start)
    complete_items = [
        {
            'kind': 'CapsuleTenant',
            'namespace': '',
            'name': 'demo',
            'uid': 'cr-uid',
            'resource_version': '2',
            'state': 'preserved',
        },
        {
            'kind': 'Namespace',
            'namespace': '',
            'name': 'demo-dev',
            'uid': 'ns-uid',
            'resource_version': '6',
            'state': 'provider_markers_transferred',
        },
        {
            'kind': 'GlobalResourceQuota',
            'namespace': '',
            'name': 'global',
            'uid': 'g-uid',
            'resource_version': '8',
            'state': 'preserved',
        },
    ]
    sha = _digest(complete_items)
    terminal = {
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'actor_user_id': 21,
        'worklist_sha256': work['inventory_sha256'],
        'event_type': 'readback_candidate',
        'readback_sha256': sha,
        'expected_count': 1,
        'observed_count': 1,
        'transferred_count': 1,
        'pending_count': 0,
        'ambiguous_count': 0,
    }
    terminal['event_sha256'] = _event_checksum(terminal)
    attempt_id = 'attempt-1'
    rows = [
        SimpleNamespace(
            event_json=start,
            event_sha256=start['event_sha256'],
            sequence=1,
            event_type='started',
            attempt_id=attempt_id,
            previous_event_sha256=None,
            worklist_sha256=work['inventory_sha256'],
        ),
        SimpleNamespace(
            event_json=terminal,
            event_sha256=terminal['event_sha256'],
            sequence=2,
            event_type='readback_candidate',
            attempt_id=attempt_id,
            previous_event_sha256=start['event_sha256'],
            worklist_sha256=work['inventory_sha256'],
        ),
    ]
    receipt = {
        'status': 'provider_handoff_verified',
        'provider_handoff_verified': True,
        'whole_scope_readback_verified': True,
        'resource_specific_consent_verified': True,
        'controller_origin_verified': False,
        'controller_generated_rbac_preserved': True,
        'provider_authority_verified': True,
        'source_worklist_sha256': work['inventory_sha256'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'attempt_id': attempt_id,
        'start_event_sha256': start['event_sha256'],
        'readback_sha256': sha,
        'actor_user_id': 21,
        'errors': [],
        'auto_retry_authorized': False,
        'verified_components': complete_items,
        'verified_resource_count': 3,
    }
    return plan, work, rows, receipt


def _mock_complete_g3_source(monkeypatch, rows, receipt):
    from app.kubernetes.tenant import capsule_handoff_ledger_review as ledger

    monkeypatch.setattr(
        ledger,
        'inspect_capsule_ledger_rows',
        lambda **_: {
            'status': 'readback_claim_requires_independent_provider_verification',
            'event_count': 2,
            'worklist_sha256': 'd' * 64,
        },
    )
    monkeypatch.setattr(
        finalizer,
        'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=_Query(rows)),
    )
    monkeypatch.setattr(
        finalizer,
        'AuditEvent',
        SimpleNamespace(query=_Query([SimpleNamespace(metadata_json=receipt)])),
    )


def test_capsule_g4_accepts_source_shape_with_foreign_rbac_preserved_but_never_auto_releases(monkeypatch):
    plan, work, rows, receipt = _ledger_and_g3_receipt()
    _mock_complete_g3_source(monkeypatch, rows, receipt)
    assert (
        finalizer._committed_full_handoff(
            tenant_id='tenant-1',
            plan=plan,
            related={},
            work=work,
            actor_user_id=21,
        )
        is receipt
    )


@pytest.mark.parametrize(
    'mutation',
    [
        lambda w, r: r.update(controller_generated_rbac_preserved=False),
        lambda w, r: r.update(controller_origin_verified=True),
        lambda w, r: r['verified_components'][0].update(resource_version='changed'),
        lambda w, r: r.update(resource_specific_consent_verified=False),
        lambda w, r: w['items'].append(
            {
                'kind': 'RoleBinding',
                'namespace': 'demo-dev',
                'name': 'kaori-rb',
                'decision': 'explicit_kaori_metadata_handoff_review',
            }
        ),
    ],
)
def test_capsule_g4_blocks_forged_origin_consent_changed_sha_and_kaori_rolebinding(monkeypatch, mutation):
    plan, work, rows, receipt = _ledger_and_g3_receipt()
    mutation(work, receipt)
    _mock_complete_g3_source(monkeypatch, rows, receipt)
    with pytest.raises(ValueError, match='canonical complete read-back proof'):
        finalizer._committed_full_handoff(
            tenant_id='tenant-1',
            plan=plan,
            related={},
            work=work,
            actor_user_id=21,
        )
