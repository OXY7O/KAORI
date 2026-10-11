"""#1229 working Capsule single-attempt executor regression contracts.

Source-authored only; do not execute until separate Developer Check/UAT approval.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.kubernetes.tenant import capsule_handoff_executor as executor


def _start():
    return {
        'contract_version': 'capsule-handoff-attempt/v1',
        'event_type': 'started',
        'attempt_id': str(uuid4()), 'sequence': 1,
        'event_at': datetime.now(UTC).isoformat(),
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 2, 'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'b' * 64,
        'worklist_sha256': 'c' * 64,
        'actor_user_id': 37,
        'previous_event_sha256': None, 'event_sha256': 'd' * 64,
        'outcome': 'unknown', 'readback_sha256': None,
        'expected_count': 1, 'observed_count': 0, 'pending_count': 0,
        'transferred_count': 0, 'ambiguous_count': 0,
        'provider_handoff_verified': False, 'release_authorized': False,
        'resume_authorized': False, 'auto_retry_authorized': False,
        'secret_material_persisted': False,
    }


def _plan():
    return {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 2, 'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'b' * 64,
        'successor_owner': 'platform-admin',
        'handoff_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
             'resource_version': '12'},
        ],
    }


def _authority():
    return {
        'provider_username': 'platform-admin',
        'provider_credential_id': 'X509SHA256=trusted',
    }


def test_capsule_execute_denies_missing_human_confirmation_before_any_provider_call(monkeypatch):
    monkeypatch.setattr(
        executor, '_exact_current_scope',
        lambda **_: pytest.fail('Provider scope must not be inspected without consent'),
    )
    with pytest.raises(ValueError, match='Explicit exact-resource'):
        executor.execute_capsule_handoff_committed(
            tenant_id='tenant-1', actor_user_id=37,
            plan_sha256='a' * 64, worklist_sha256='c' * 64,
            confirmed=False,
        )


def test_capsule_terminal_refuses_fake_complete_readback_before_any_ledger_write(monkeypatch):
    monkeypatch.setattr(
        executor, '_write_ledger_event',
        lambda **_: pytest.fail('No terminal event may be persisted from missing scope'),
    )
    with pytest.raises(ValueError, match='pending objects'):
        executor._terminal(
            start=_start(), plan=_plan(), related={},
            complete=True, items=[], errors=[],
            authority=_authority(),
        )


def test_capsule_partial_terminal_records_only_observed_transfers_and_forbids_release(monkeypatch):
    observed = []
    class _FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def begin(self):
            return self
        def add(self, row):
            observed.append(row)
    monkeypatch.setattr(executor, '_write_ledger_event', lambda **kw: observed.append(kw['event']))
    monkeypatch.setattr(executor, 'Session', lambda engine: _FakeSession())
    monkeypatch.setattr(executor, 'db', SimpleNamespace(engine=object()))
    monkeypatch.setattr(executor, 'AuditEvent', lambda **kwargs: kwargs)
    receipt = executor._terminal(
        start=_start(), plan=_plan(), related={}, complete=False,
        items=[], errors=['Namespace/demo-dev: TimeoutError'],
        authority=_authority(),
    )
    event, audit = observed
    assert event['event_type'] == 'partial'
    assert event['observed_count'] == 0
    assert event['ambiguous_count'] == 0
    assert event['readback_sha256'] is None
    assert receipt['status'] == 'partial_handoff_recovery_required'
    assert receipt['provider_handoff_verified'] is False
    assert receipt['whole_scope_readback_verified'] is False
    assert receipt['provider_mutation_performed'] is None
    assert receipt['auto_retry_authorized'] is False
    assert receipt['release_authorized'] is False
    assert audit['metadata_json']['errors'] == ['Namespace/demo-dev: TimeoutError']


def test_capsule_terminal_success_never_marks_governance_released(monkeypatch):
    events = []
    class _FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def begin(self):
            return self
        def add(self, value):
            events.append(value)
    monkeypatch.setattr(executor, '_write_ledger_event', lambda **kw: events.append(kw['event']))
    monkeypatch.setattr(executor, 'Session', lambda engine: _FakeSession())
    monkeypatch.setattr(executor, 'db', SimpleNamespace(engine=object()))
    monkeypatch.setattr(executor, 'AuditEvent', lambda **kw: kw)
    receipt = executor._terminal(
        start=_start(), plan=_plan(), related={}, complete=True,
        items=[
            {'kind': 'Namespace', 'namespace': '', 'name': 'demo-dev',
             'uid': 'ns-uid', 'resource_version': '14',
             'state': 'provider_markers_transferred'},
            {'kind': 'CapsuleTenant', 'namespace': '', 'name': 'demo',
             'uid': 'cr-uid', 'resource_version': '12', 'state': 'preserved'},
        ],
        errors=[], authority=_authority(),
    )
    assert events[0]['event_type'] == 'readback_candidate'
    assert events[0]['observed_count'] == 1
    assert receipt['status'] == 'provider_handoff_verified'
    assert receipt['verified_resource_count'] == 2
    assert receipt['controller_origin_verified'] is False
    assert receipt['controller_generated_rbac_preserved'] is True
    assert receipt['release_authorized'] is False
    assert receipt['auto_retry_authorized'] is False


def test_capsule_related_quota_and_foreign_rolebinding_cannot_be_promoted_from_preview(monkeypatch):
    monkeypatch.setattr(
        executor, 'build_capsule_handoff_worklist', lambda **_: {
            'inventory_sha256': 'c' * 64, 'items': [
                {'namespace': '', 'kind': 'Namespace', 'name': 'demo-dev',
                 'uid': 'ns-uid', 'resource_version': '7',
                 'decision': 'candidate_kaori_metadata_handoff_review'},
                {'namespace': 'demo-dev', 'kind': 'RoleBinding', 'name': 'rb',
                 'uid': 'rb-uid', 'resource_version': '3',
                 'decision': 'explicit_kaori_metadata_handoff_review'},
            ],
        },
    )
    # Exact X.509 actor, current preflight and accepted Release plan are
    # mandatory; a preview alone is never a sufficient provider capability.
    monkeypatch.setattr(executor, 'require_platform_admin_actor', lambda *_: None)
    monkeypatch.setattr(executor, 'latest_release_handoff_plan', lambda *_: _plan())
    monkeypatch.setattr(executor, 'latest_release_handoff_approval', lambda *_: {
        'plan_sha256': 'a' * 64,
        'status': 'acknowledged_pending_provider_handoff',
        'approved_by': 12, 'approved_at': datetime.now(UTC).isoformat(),
    })
    monkeypatch.setattr(executor, '_plan_hash', lambda *_: 'a' * 64)
    monkeypatch.setattr(executor, 'require_current_capsule_acceptance', lambda **_: {
        'accepted_by': 37,
    })
    tenant = SimpleNamespace(
        lifecycle_status='ready', provider_key='capsule',
        provider_state='capsule', reconciliation_authority='capsule',
        ownership_status='adopted', cluster_id='cluster-1', generation=2,
    )
    monkeypatch.setattr(
        executor, 'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda *_: tenant)),
    )
    monkeypatch.setattr(executor, '_release_dependency_counts', lambda *_: {'credentials': 0})
    preflight = {
        'handoff_fingerprint': 'b' * 64,
        'handoff_components': _plan()['handoff_components'],
        'live_provider_identity': None, 'dependency_counts': None,
        'capsule_related_inventory': {'blockers': [], 'global_quota': {'blockers': []},
                                      'rbac_lineage': {'blockers': []}},
        'blockers': [],
    }
    monkeypatch.setattr(
        executor, 'latest_release_handoff_plan',
        lambda *_: {**_plan(), 'provider': 'capsule', 'requested_by': 10,
                    'requested_at': datetime.now(UTC).isoformat(),
                    'provider_identity': None, 'dependency_counts': None},
    )
    monkeypatch.setattr(executor, 'review_tenant_release_preflight_committed',
                        lambda **_: preflight)
    monkeypatch.setattr(executor, '_can_confirm_plan', lambda *_: None)
    with pytest.raises(ValueError, match='unverified KAORI RoleBinding origin'):
        executor._exact_current_scope(
            tenant_id='tenant-1', actor_user_id=37, plan_sha256='a' * 64,
            expected_worklist_sha256='c' * 64,
        )


def test_capsule_foreign_namespace_preservation_requires_full_provider_invariants(monkeypatch):
    from copy import deepcopy

    def provider_namespace():
        return SimpleNamespace(
            metadata=SimpleNamespace(
                name='external-ns', uid='ns-uid', resource_version='rv-1',
                labels={'capsule.clastix.io/tenant': 'demo', 'foreign/owner': 'operator'},
                annotations={'external/annotation': 'keep'},
                owner_references=[{'uid': 'owner-uid', 'kind': 'Tenant'}],
                finalizers=['external.io/cleanup'],
            ),
            spec={'finalizers': ['kubernetes']},
        )

    source = provider_namespace()
    executor._verify_preserved_foreign_namespace(
        before=source, current=deepcopy(source),
    )
    mutations = [
        lambda obj: setattr(obj.metadata, 'resource_version', 'rv-2'),
        lambda obj: obj.metadata.labels.update({'unexpected': 'value'}),
        lambda obj: obj.metadata.annotations.update({'external/annotation': 'changed'}),
        lambda obj: obj.metadata.owner_references[0].update(uid='different-owner'),
        lambda obj: obj.metadata.finalizers.append('unknown/finalizer'),
        lambda obj: obj.spec['finalizers'].append('unapproved'),
    ]
    for mutation in mutations:
        current = deepcopy(source)
        mutation(current)
        with pytest.raises(ValueError, match='Foreign Capsule Namespace identity, spec'):
            executor._verify_preserved_foreign_namespace(
                before=source, current=current,
            )


def test_capsule_route_and_ui_require_exact_digest_and_separate_confirmation():
    from pathlib import Path

    route = Path('app/kubernetes/tenant/routes.py').read_text()
    section = route.split('def execute_capsule_handoff_route', 1)[1].split(
        '\n@tenant_bp.post', 1,
    )[0]
    assert '_csrf()' in section
    assert "worklist_sha256=str(request.form.get('worklist_sha256')" in section
    assert "confirm_capsule_handoff_execute') == 'execute'" in section
    ui = Path('app/templates/kubernetes/tenant/partials/_tenant_management_detail.html').read_text()
    assert 'tenant.execute_capsule_handoff_route' in ui
    assert 'capsule_preview.source_worklist_sha256' in ui
    assert 'capsule_preview.unverified_kaori_rolebinding_origin' in ui
