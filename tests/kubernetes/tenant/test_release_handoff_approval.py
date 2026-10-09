from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan,
    _plan_hash,
    _complete_provider_snapshot,
    _valid_reference,
    approve_release_handoff_plan_committed,
    prepare_release_handoff_plan_committed,
)


def _snapshot(*, status: str = 'blocked', blockers: list[str] | None = None) -> dict:
    snapshot = {
        'tenant_id': 'tenant-a',
        'cluster_id': 'cluster-a',
        'generation': 2,
        'provider': 'native_kubernetes',
        'status': status,
        'checked_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': '',
        'live_provider_identity': [
            {
                'kind': 'Namespace',
                'name': 'sandbox',
                'uid': 'namespace-uid',
                'resource_version': '5',
            }
        ],
        'handoff_components': [
            {
                'kind': 'Namespace', 'name': 'sandbox', 'uid': 'namespace-uid',
                'resource_version': '5', 'handoff': 'external_acceptance_required',
                'ownership': 'kaori_marker_correlated',
            }
        ],
        'handoff_required_count': 1,
        'dependency_counts': {
            'Access Grants': 0, 'credentials': 0, 'Memberships': 0,
            'enabled Groups': 0, 'advanced capabilities': 0,
            'managed resources': 0, 'domain reservations': 0,
            'exposure policies': 0,
        },
        'blockers': blockers if blockers is not None else [
            'Adoption performed KAORI-owned provider mutations. '
            'Complete independently verified allocation/policy handoff before Release.',
            'sandbox KAORI-linked allocation ownership requires independently approved '
            'external handoff and provider read-back.',
        ],
    }
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    return snapshot


def _plan_from_snapshot(snapshot: dict) -> dict:
    plan = {
        'status': 'pending_independent_approval',
        'tenant_id': snapshot['tenant_id'],
        'cluster_id': snapshot['cluster_id'],
        'generation': snapshot['generation'],
        'provider': snapshot['provider'],
        'handoff_fingerprint': snapshot['handoff_fingerprint'],
        'provider_identity': snapshot['live_provider_identity'],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-2026-109',
        'requested_by': 42,
        'requested_at': datetime.now(UTC).isoformat(),
    }
    plan['plan_sha256'] = _plan_hash(plan)
    return plan


def test_handoff_plan_acceptance_requires_only_expected_handoff_blockers():
    _can_confirm_plan(_snapshot())


def test_proven_namespace_mutation_requires_handoff_but_unknown_provenance_blocks_plan():
    approved_handoff_blocker = (
        'sandbox has KAORI-mutated Namespace provider controls; '
        'independently approved external handoff is required.'
    )
    _can_confirm_plan(_snapshot(blockers=[approved_handoff_blocker]))

    with pytest.raises(ValueError, match='Unresolved'):
        _can_confirm_plan(_snapshot(blockers=[
            'sandbox has missing or unverified provider mutation provenance; '
            'investigate before approving handoff.'
        ]))


@pytest.mark.parametrize('blocker', [
    'Namespace/sandbox provider UID mismatch.',
    'External Capsule access observation is stale.',
    'Native provider is unavailable.',
    'sandbox allocation hash changed since committed KAORI evidence.',
    'sandbox has inconsistent provider ownership markers.',
])
def test_handoff_approval_blocks_other_governance_or_provider_failures(blocker):
    with pytest.raises(ValueError, match='Unresolved'):
        _can_confirm_plan(_snapshot(blockers=[blocker]))


def test_handoff_approval_rejects_active_dependencies():
    snapshot = _snapshot()
    snapshot['dependency_counts']['Access Grants'] = 1
    with pytest.raises(ValueError, match='Clear all active'):
        _can_confirm_plan(snapshot)


def test_handoff_approval_rejects_foreign_or_unverified_ownership():
    snapshot = _snapshot()
    snapshot['handoff_components'][0]['handoff'] = 'owner_review_required'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    with pytest.raises(ValueError, match='Conflicting provider ownership'):
        _can_confirm_plan(snapshot)

    snapshot['handoff_components'][0]['handoff'] = 'observe_only'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    snapshot['handoff_required_count'] = 0
    with pytest.raises(ValueError, match='No verified KAORI-linked resource'):
        _can_confirm_plan(snapshot)


def test_handoff_evidence_requires_all_correlated_namespace_identities():
    snapshot = _snapshot()
    snapshot['live_provider_identity'].append({
        'kind': 'Namespace', 'name': 'second', 'uid': 'other',
        'resource_version': '1',
    })
    with pytest.raises(ValueError, match='coverage'):
        _complete_provider_snapshot(snapshot)


@pytest.mark.parametrize('duplicate_target', ['provider_identity', 'handoff_component'])
def test_handoff_rejects_ambiguous_duplicate_provider_identity(duplicate_target):
    snapshot = _snapshot()
    if duplicate_target == 'provider_identity':
        snapshot['live_provider_identity'].append({
            **snapshot['live_provider_identity'][0], 'uid': 'replacement-generation',
        })
    else:
        snapshot['handoff_components'].append({
            **snapshot['handoff_components'][0], 'uid': 'replacement-generation',
        })
        snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    with pytest.raises(ValueError, match='duplicated or ambiguous'):
        _complete_provider_snapshot(snapshot)


def test_handoff_evidence_rejects_stale_and_incomplete_provider_metadata():
    snapshot = _snapshot()
    snapshot['checked_at'] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with pytest.raises(ValueError, match='Refresh'):
        _complete_provider_snapshot(snapshot)

    snapshot = _snapshot()
    snapshot['handoff_components'][0]['uid'] = ''
    with pytest.raises(ValueError, match='incomplete'):
        _complete_provider_snapshot(snapshot)


def test_handoff_owner_and_change_references_are_bounded_and_nonsecret():
    assert _valid_reference('platform-team', name='Successor') == 'platform-team'
    assert _valid_reference('CHG-2026-109', name='Change') == 'CHG-2026-109'
    for value in ('', 'ab', 'space separated', '<script>', 'x' * 121):
        with pytest.raises(ValueError):
            _valid_reference(value, name='Successor')


def test_second_approver_cannot_be_handoff_requester(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = _plan_from_snapshot(_snapshot())
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    with pytest.raises(ValueError, match='independent approver'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=42,
            plan_sha256=plan['plan_sha256'], approved=True,
        )


def test_second_approver_requires_same_latest_plan_and_fresh_window(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = _plan_from_snapshot(_snapshot())
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    with pytest.raises(ValueError, match='plan changed'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256='b' * 64, approved=True,
        )
    plan['requested_at'] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    plan['plan_sha256'] = _plan_hash(plan)
    with pytest.raises(ValueError, match='expired'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256=plan['plan_sha256'], approved=True,
        )


def test_second_approver_requires_explicit_acknowledgement():
    with pytest.raises(ValueError, match='acknowledgement'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256='a' * 64, approved=False,
        )


class _FakeSession:
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.events = []
        self.commits = 0

    def get(self, model, tenant_id):
        return self.tenant

    def add(self, event):
        self.events.append(event)

    def commit(self):
        self.commits += 1


def test_prepare_handoff_commits_plan_without_provider_mutation(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    tenant = SimpleNamespace(ownership_status='adopted', lifecycle_status='ready')
    class _TenantQuery:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return tenant

    session = _FakeSession(tenant)
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_TenantQuery()))
    monkeypatch.setattr(module, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'review_tenant_release_preflight_committed', lambda **_: _snapshot())

    result = prepare_release_handoff_plan_committed(
        tenant_id='tenant-a', actor_user_id=42,
        successor_owner='platform-team', change_reference='CHG-2026-109',
    )
    assert len(result['plan_sha256']) == 64
    assert result['status'] == 'pending_independent_approval'
    assert result['provider_mutation_performed'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert session.commits == 1
    assert len(session.events) == 1
    assert session.events[0].action == 'tenant.release.handoff_plan_prepared'
    assert session.events[0].target_id == 'tenant-a'


def test_independent_handoff_approval_commits_pending_provider_state(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    snapshot = _snapshot()
    plan = _plan_from_snapshot(snapshot)
    class _Query:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return SimpleNamespace(lifecycle_status='ready', ownership_status='adopted')

    session = _FakeSession()
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_Query()))
    monkeypatch.setattr(module, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)
    monkeypatch.setattr(module, 'review_tenant_release_preflight_committed', lambda **_: snapshot)

    result = approve_release_handoff_plan_committed(
        tenant_id='tenant-a', actor_user_id=43,
        plan_sha256=plan['plan_sha256'], approved=True,
    )
    assert result['status'] == 'acknowledged_pending_provider_handoff'
    assert result['requested_by'] == 42 and result['approved_by'] == 43
    assert result['provider_mutation_performed'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert session.commits == 1
    assert session.events[0].action == 'tenant.release.handoff_acknowledged'


def test_handoff_approval_rejects_partial_dependency_ledger_and_forged_count():
    snapshot = _snapshot()
    snapshot['dependency_counts'].pop('exposure policies')
    with pytest.raises(ValueError, match='every active Tenant dependency'):
        _can_confirm_plan(snapshot)

    snapshot = _snapshot()
    snapshot['handoff_required_count'] = 0
    with pytest.raises(ValueError, match='count is inconsistent'):
        _can_confirm_plan(snapshot)


def test_handoff_approval_rejects_changed_component_fingerprint_and_unknown_ownership():
    snapshot = _snapshot()
    snapshot['handoff_components'][0]['resource_version'] = '6'
    with pytest.raises(ValueError, match='fingerprint'):
        _can_confirm_plan(snapshot)

    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    snapshot['handoff_components'][0]['handoff'] = 'unknown'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    with pytest.raises(ValueError, match='Unsupported or missing ownership'):
        _can_confirm_plan(snapshot)
