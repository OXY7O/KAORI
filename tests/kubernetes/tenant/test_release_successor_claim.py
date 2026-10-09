from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import release_successor_claim as module
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def _plan_and_approval():
    components = [{
        'kind': 'Namespace', 'name': 'dev', 'namespace': 'dev', 'uid': 'ns-1',
        'resource_version': '8', 'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }]
    identity = [{'kind': 'Namespace', 'name': 'dev', 'uid': 'ns-1', 'resource_version': '8'}]
    plan = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1', 'generation': 2,
        'provider': 'native_kubernetes', 'provider_identity': identity,
        'handoff_fingerprint': handoff_fingerprint(components),
        'successor_owner': 'platform-team', 'change_reference': 'CHG-2026-109',
        'requested_by': 1, 'requested_at': datetime.now(UTC).isoformat(),
    }
    plan['plan_sha256'] = _plan_hash(plan)
    approval = {
        'plan_sha256': plan['plan_sha256'],
        'status': 'acknowledged_pending_provider_handoff',
        'requested_by': 1, 'approved_by': 2,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_handoff_verified': False, 'release_authorized': False,
    }
    snapshot = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1', 'generation': 2,
        'provider': 'native_kubernetes', 'status': 'blocked',
        'checked_at': datetime.now(UTC).isoformat(),
        'handoff_components': components, 'live_provider_identity': identity,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'handoff_required_count': 1,
        'dependency_counts': {
            'credentials': 0, 'Access Grants': 0, 'Memberships': 0,
            'enabled Groups': 0, 'managed resources': 0,
            'advanced capabilities': 0, 'domain reservations': 0,
            'exposure policies': 0,
        },
        'blockers': [
            'Adoption performed KAORI-owned provider mutations.',
            'dev KAORI-linked allocation ownership requires independently approved external handoff and provider read-back.',
        ],
    }
    return plan, approval, snapshot


@pytest.mark.parametrize('damage', [
    lambda p, a: a.update(approved_by=1),
    lambda p, a: a.update(status='pending_independent_approval'),
    lambda p, a: a.update(handoff_fingerprint='stale'),
    lambda p, a: a.update(provider_handoff_verified=True),
    lambda p, a: a.update(release_authorized=True),
    lambda p, a: p.update(successor_owner='forged'),
    lambda p, a: a.update(plan_sha256='a' * 64),
])
def test_external_reference_refuses_unapproved_or_tampered_handoff(damage):
    plan, approval, _ = _plan_and_approval()
    damage(plan, approval)
    with pytest.raises(ValueError, match='independently acknowledged'):
        module._require_matching_approval(
            tenant_id='tenant-1', plan_sha256=plan['plan_sha256'],
            plan=plan, approval=approval,
        )


class _Session:
    def __init__(self, tenant):
        self.tenant = tenant
        self.events = []
        self.commits = 0

    def get(self, model, key):
        return self.tenant

    def add(self, event):
        self.events.append(event)

    def commit(self):
        self.commits += 1


def _mock_context(monkeypatch, *, change_provider=False, previous=None):
    plan, approval, snapshot = _plan_and_approval()
    tenant = SimpleNamespace(
        lifecycle_status='ready', ownership_status='adopted',
        cluster_id='cluster-1', generation=2, provider_key='native_kubernetes',
    )

    class _Query:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return tenant

    session = _Session(tenant)
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_Query()))
    monkeypatch.setattr(module, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: approval)
    prior = {'plan_sha256': plan['plan_sha256']} if previous == 'same_plan' else previous
    monkeypatch.setattr(module, 'latest_release_successor_claim', lambda _: prior)
    if change_provider:
        snapshot['live_provider_identity'] = [{
            'kind': 'Namespace', 'name': 'dev', 'uid': 'replaced', 'resource_version': '9',
        }]
    monkeypatch.setattr(module, 'review_tenant_release_preflight_committed', lambda **_: snapshot)
    return plan, session


def test_successor_reference_is_audited_but_never_authorizes_transfer(monkeypatch):
    plan, session = _mock_context(monkeypatch)
    receipt = module.record_release_successor_claim_committed(
        tenant_id='tenant-1', actor_user_id=3,
        plan_sha256=plan['plan_sha256'], successor_reference='EXT-ACK-2026-123',
    )
    assert receipt['status'] == 'external_reference_unverified'
    assert receipt['external_successor_verified'] is False
    assert receipt['provider_handoff_verified'] is False
    assert receipt['release_authorized'] is False
    assert receipt['provider_mutation_performed'] is False
    assert session.commits == 1
    assert session.events[0].action == 'tenant.release.successor_reference_recorded'


def test_successor_reference_rejects_stale_provider_and_duplicate(monkeypatch):
    plan, session = _mock_context(monkeypatch, change_provider=True)
    with pytest.raises(ValueError, match='Provider changed'):
        module.record_release_successor_claim_committed(
            tenant_id='tenant-1', actor_user_id=3,
            plan_sha256=plan['plan_sha256'], successor_reference='EXT-ACK-2026-123',
        )
    assert session.commits == 0
    plan, session = _mock_context(monkeypatch, previous='same_plan')
    with pytest.raises(ValueError, match='already recorded'):
        module.record_release_successor_claim_committed(
            tenant_id='tenant-1', actor_user_id=3,
            plan_sha256=plan['plan_sha256'], successor_reference='EXT-ACK-2026-123',
        )
    assert session.commits == 0


@pytest.mark.parametrize('reference', ['', '<script>', 'hello world', 'a' * 121])
def test_successor_reference_rejects_unsafe_input(reference):
    with pytest.raises(ValueError, match='External successor reference'):
        module.record_release_successor_claim_committed(
            tenant_id='tenant-1', actor_user_id=3,
            plan_sha256='a' * 64, successor_reference=reference,
        )
