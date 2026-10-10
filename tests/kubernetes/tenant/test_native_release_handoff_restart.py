"""Governed restart of expired approved Native handoff plan (#1057)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import release_handoff_approval as service
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def snapshot():
    components = [{
        'kind': 'Namespace', 'name': 'sandbox', 'uid': 'uid-1',
        'resource_version': '21', 'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }]
    return {
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 3, 'provider': 'native_kubernetes',
        'status': 'blocked',
        'checked_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': handoff_fingerprint(components),
        'live_provider_identity': [{
            'kind': 'Namespace', 'name': 'sandbox', 'uid': 'uid-1', 'resource_version': '21',
        }],
        'handoff_components': components,
        'handoff_required_count': 1,
        'dependency_counts': {
            'Access Grants': 0, 'credentials': 0, 'Memberships': 0,
            'enabled Groups': 0, 'managed resources': 0,
            'advanced capabilities': 0, 'domain reservations': 0,
            'exposure policies': 0,
        },
        'blockers': ['Adoption performed KAORI-owned provider mutations.'],
    }


def plan(snapshot_data, *, expired=True):
    data = {
        'tenant_id': snapshot_data['tenant_id'],
        'cluster_id': snapshot_data['cluster_id'],
        'generation': snapshot_data['generation'],
        'provider': snapshot_data['provider'],
        'status': 'pending_independent_approval',
        'handoff_fingerprint': snapshot_data['handoff_fingerprint'],
        'provider_identity': snapshot_data['live_provider_identity'],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-2026-002',
        'requested_by': 42,
        'requested_at': (
            datetime.now(UTC) - timedelta(hours=1) if expired else datetime.now(UTC)
        ).isoformat(),
    }
    data['plan_sha256'] = service._plan_hash(data)
    return data


def approval(plan_data, *, expired=True):
    return {
        'plan_sha256': plan_data['plan_sha256'],
        'requested_by': 42, 'approved_by': 43,
        'status': 'acknowledged_pending_provider_handoff',
        'handoff_fingerprint': plan_data['handoff_fingerprint'],
        'approved_at': (
            datetime.now(UTC) - timedelta(hours=1) if expired else datetime.now(UTC)
        ).isoformat(),
        'provider_handoff_verified': False, 'release_authorized': False,
    }


def prepare(monkeypatch, *, expired=True, actor=42, readback=None, mutate=None):
    existing = snapshot()
    data = plan(existing, expired=expired)
    acknowledged = approval(data, expired=expired)
    tenant = SimpleNamespace(
        cluster_id='cluster-a', generation=3,
        provider_key='native_kubernetes',
        reconciliation_authority='native_kubernetes',
        ownership_status='adopted', lifecycle_status='ready',
    )

    class Query:
        def filter_by(self, **_):
            return self
        def with_for_update(self):
            return self
        def one_or_none(self):
            return tenant

    class Session:
        def __init__(self):
            self.events = []
            self.commits = 0
        def add(self, row):
            self.events.append(row)
        def commit(self):
            self.commits += 1

    session = Session()
    monkeypatch.setattr(service, 'Tenant', SimpleNamespace(query=Query()))
    monkeypatch.setattr(service, 'AuditEvent', lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(service, 'latest_release_handoff_plan', lambda _: data)
    monkeypatch.setattr(service, 'latest_release_handoff_approval', lambda _: acknowledged)
    monkeypatch.setattr(
        service, 'review_tenant_release_preflight_committed',
        lambda **_: mutate(existing) if mutate else existing,
    )
    from app.kubernetes.tenant import native_handoff_readback
    monkeypatch.setattr(
        native_handoff_readback, 'latest_native_handoff_readback',
        lambda _: readback,
    )
    result = service.restart_expired_native_release_handoff_plan_committed(
        tenant_id='tenant-a', actor_user_id=actor,
        plan_sha256=data['plan_sha256'], confirmed=True,
    )
    return result, data, session


def test_expired_acknowledged_plan_gets_new_sha_and_independent_review(monkeypatch):
    renewed, old, session = prepare(monkeypatch)
    assert renewed['plan_sha256'] != old['plan_sha256']
    assert renewed['supersedes_plan_sha256'] == old['plan_sha256']
    assert renewed['status'] == 'pending_independent_approval'
    assert renewed['requested_by'] == 42
    assert renewed['provider_handoff_verified'] is False
    assert renewed['release_authorized'] is False
    assert renewed['secret_material_persisted'] is False
    assert session.commits == 1
    assert session.events[0].action == 'tenant.release.handoff_plan_restarted'


def test_requester_cannot_restart_current_review(monkeypatch):
    with pytest.raises(ValueError, match='still current'):
        prepare(monkeypatch, expired=False)


def test_wrong_requester_cannot_restart_acknowledged_plan(monkeypatch):
    with pytest.raises(ValueError, match='Only the original requester'):
        prepare(monkeypatch, actor=55)


def test_provider_readback_blocks_restart_even_when_expired(monkeypatch):
    readback = {'plan_sha256': plan(snapshot())['plan_sha256']}
    # Force consistent old SHA on the same plan by setting the spy after creation
    # instead use a returning read-back receipt of whatever current plan exists
    from app.kubernetes.tenant import native_handoff_readback
    monkeypatch.setattr(
        native_handoff_readback, 'latest_native_handoff_readback',
        lambda _: {'plan_sha256': service.latest_release_handoff_plan('tenant-a')['plan_sha256']},
    )
    with pytest.raises(ValueError, match='read-back'):
        prepare(monkeypatch)


def test_changed_provider_inventory_blocks_restart(monkeypatch):
    def changed(data):
        return {**data, 'handoff_fingerprint': 'another-inventory'}
    with pytest.raises(ValueError, match='Provider inventory changed'):
        prepare(monkeypatch, mutate=changed)


def test_restart_requires_explicit_confirmation(monkeypatch):
    with pytest.raises(ValueError, match='explicit'):
        service.restart_expired_native_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=42,
            plan_sha256='a' * 64, confirmed=False,
        )


def test_stale_reapproval_cannot_reuse_original_external_reference(monkeypatch):
    renewed, old, _ = prepare(monkeypatch)
    assert renewed['plan_sha256'] != old['plan_sha256']
    assert renewed.get('successor_reference') is None
    assert renewed.get('approved_by') is None
