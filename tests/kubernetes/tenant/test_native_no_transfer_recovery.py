"""Fail-closed Native failed-before-write recovery contracts (#1104).

No Kubernetes mutation; provider reads are always mocked in focused tests.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import native_no_transfer_recovery as recovery


class Column:
    def __eq__(self, other):
        return self

    def in_(self, items):
        return self

    def asc(self):
        return self

    def desc(self):
        return self


class HistoryQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.rows


def plan():
    return {
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 2, 'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'fingerprint',
        'requested_by': 42, 'successor_owner': 'platform-team',
        'handoff_components': [{
            'kind': 'Namespace', 'name': 'demo', 'uid': 'uid-1',
            'resource_version': '21', 'handoff': 'external_acceptance_required',
            'ownership': 'kaori_marker_correlated',
        }],
    }


def history(plan_data, *, mutate=False):
    started = {
        'status': 'in_progress',
        'plan_sha256': plan_data['plan_sha256'],
        'handoff_fingerprint': plan_data['handoff_fingerprint'],
        'release_authorized': False,
    }
    failed = {
        'status': 'partial_handoff_recovery_required',
        'tenant_id': plan_data['tenant_id'],
        'cluster_id': plan_data['cluster_id'],
        'generation': plan_data['generation'],
        'plan_sha256': plan_data['plan_sha256'],
        'handoff_fingerprint': plan_data['handoff_fingerprint'],
        'errors': ['ResourceQuota/tenant-resource-quota: ValueError'],
        'verified_count': 0, 'expected_component_count': 1,
        'verified_components': [], 'provider_mutation_performed': mutate,
        'provider_handoff_verified': False, 'release_authorized': False,
    }
    return [
        SimpleNamespace(
            id=1, actor_user_id=43,
            target_type=recovery._EXECUTOR_TARGET,
            action='tenant.release.native_handoff_started', metadata_json=started,
        ),
        SimpleNamespace(
            id=2, actor_user_id=43,
            target_type=recovery._EXECUTOR_TARGET,
            action='tenant.release.native_handoff_recovery_required', metadata_json=failed,
        ),
    ]


def set_history(monkeypatch, rows):
    audit = SimpleNamespace(
        id=Column(), target_type=Column(), target_id=Column(),
        query=HistoryQuery(rows),
    )
    monkeypatch.setattr(recovery, 'AuditEvent', audit)


def test_exact_failed_before_write_history_is_eligible_for_assessment(monkeypatch):
    p = plan()
    set_history(monkeypatch, history(p))
    result = recovery._source_history(p['tenant_id'], p)
    assert len(result['digest']) == 64
    assert result['executor_actor_id'] == 43
    assert result['failed_event_id'] == 2


@pytest.mark.parametrize('alteration', ['mutated', 'missing_failure', 'readback', 'verified_one', 'unknown'])
def test_unsafe_or_ambiguous_history_is_never_recoverable(monkeypatch, alteration):
    p = plan()
    rows = history(p, mutate=alteration == 'mutated')
    if alteration == 'missing_failure':
        rows.pop()
    elif alteration == 'readback':
        rows.append(SimpleNamespace(
            id=3, actor_user_id=43,
            target_type=recovery._READBACK_TARGET,
            action='tenant.release.native_handoff_readback_observed',
            metadata_json={'plan_sha256': p['plan_sha256'], 'observed_count': 0},
        ))
    elif alteration == 'verified_one':
        rows[-1].metadata_json['verified_count'] = 1
    elif alteration == 'unknown':
        rows[-1].metadata_json['plan_sha256'] = None
    set_history(monkeypatch, rows)
    with pytest.raises(ValueError):
        recovery._source_history(p['tenant_id'], p)


def assessed(p, *, stale=False):
    now = (datetime.now(UTC) - timedelta(hours=1) if stale else datetime.now(UTC)).isoformat()
    row = {
        'status': 'verified_no_transfer_pending_independent_review',
        'plan_sha256': p['plan_sha256'],
        'handoff_fingerprint': p['handoff_fingerprint'],
        'assessed_by': 42, 'executor_actor_id': 43,
        'history_digest': 'f' * 64, 'provider_proof_sha256': 'e' * 64,
        'failed_event_id': 2, 'assessed_at': now,
    }
    row['assessment_sha256'] = recovery._sha(row)
    return row


class LockedTenantQuery:
    def filter_by(self, **kwargs):
        return self

    def with_for_update(self):
        return self

    def one_or_none(self):
        return SimpleNamespace(generation=2)


def setup_authorize(monkeypatch, *, stale=False):
    p = plan()
    a = assessed(p, stale=stale)
    monkeypatch.setattr(recovery, '_require_expired_plan', lambda *args: p)
    monkeypatch.setattr(recovery, 'latest_no_transfer_assessment', lambda *args: a)
    monkeypatch.setattr(recovery, 'latest_no_transfer_decision', lambda *args: None)
    monkeypatch.setattr(recovery, '_source_history', lambda *args: {'digest': a['history_digest']})
    monkeypatch.setattr(recovery, 'Tenant', SimpleNamespace(query=LockedTenantQuery()))
    class Session:
        events = []
        def add(self, item):
            self.events.append(item)
        def commit(self):
            pass
    session = Session()
    monkeypatch.setattr(recovery, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(recovery, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    return p, a, session


@pytest.mark.parametrize('actor', [42, 43])
def test_requester_or_executor_cannot_self_authorize_recovery(monkeypatch, actor):
    p, a, _ = setup_authorize(monkeypatch)
    with pytest.raises(ValueError, match='must differ'):
        recovery.authorize_native_no_transfer_recovery_committed(
            tenant_id=p['tenant_id'], actor_user_id=actor,
            plan_sha256=p['plan_sha256'],
            assessment_sha256=a['assessment_sha256'], confirmed=True,
        )


def test_independent_third_operator_can_authorize_only_new_restart(monkeypatch):
    p, a, session = setup_authorize(monkeypatch)
    decision = recovery.authorize_native_no_transfer_recovery_committed(
        tenant_id=p['tenant_id'], actor_user_id=44,
        plan_sha256=p['plan_sha256'],
        assessment_sha256=a['assessment_sha256'], confirmed=True,
    )
    assert decision['authorized_by'] == 44
    assert decision['assessment_sha256'] == a['assessment_sha256']
    assert decision['release_authorized'] is False
    assert decision['provider_mutation_performed'] is False
    assert session.events[0].action == 'tenant.release.native_no_transfer_authorized'


def test_expired_assessment_or_mismatched_sha_blocks_independent_decision(monkeypatch):
    p, a, _ = setup_authorize(monkeypatch, stale=True)
    with pytest.raises(ValueError, match='Current exact'):
        recovery.authorize_native_no_transfer_recovery_committed(
            tenant_id=p['tenant_id'], actor_user_id=44,
            plan_sha256=p['plan_sha256'],
            assessment_sha256=a['assessment_sha256'], confirmed=True,
        )
    with pytest.raises(ValueError, match='Current exact'):
        recovery.authorize_native_no_transfer_recovery_committed(
            tenant_id=p['tenant_id'], actor_user_id=44,
            plan_sha256=p['plan_sha256'],
            assessment_sha256='b' * 64, confirmed=True,
        )


def test_decision_requires_same_fresh_actor_separated_evidence(monkeypatch):
    p, a, _ = setup_authorize(monkeypatch)
    d = {
        'status': 'authorized_for_requester_restart',
        'plan_sha256': p['plan_sha256'],
        'handoff_fingerprint': p['handoff_fingerprint'],
        'assessment_sha256': a['assessment_sha256'],
        'history_digest': a['history_digest'],
        'provider_proof_sha256': a['provider_proof_sha256'],
        'assessed_by': 42, 'authorized_by': 44,
        'authorized_at': datetime.now(UTC).isoformat(),
    }
    monkeypatch.setattr(recovery, 'latest_no_transfer_decision', lambda *args: d)
    monkeypatch.setattr(
        recovery, '_source_history',
        lambda *args: {
            'digest': a['history_digest'], 'executor_actor_id': 43,
            'failed_event_id': 2,
        },
    )
    assert recovery.require_authorized_no_transfer_restart(
        tenant_id=p['tenant_id'], plan=p, actor_user_id=42,
    ) == d
    d['authorized_by'] = 43
    with pytest.raises(ValueError, match='absent or expired'):
        recovery.require_authorized_no_transfer_restart(
            tenant_id=p['tenant_id'], plan=p, actor_user_id=42,
        )
