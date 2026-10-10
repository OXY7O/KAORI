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
        'handoff_components': snapshot_data['handoff_components'],
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



def canonical_no_transfer_readback(plan_data):
    component = plan_data['handoff_components'][0]
    observed = {
        'namespace': component.get('namespace'), 'kind': component['kind'],
        'name': component['name'], 'uid': component['uid'],
        'resource_version': component['resource_version'],
        'state': 'pending_provider_transfer', 'spec_preserved': True,
        'foreign_metadata_preserved': True,
    }
    recovery = {
        'status': 'provider_handoff_not_started',
        'components': [observed], 'transferred_count': 0,
        'pending_count': 1, 'provider_spec_preserved': True,
        'provider_resource_deleted': False, 'successor_consent_verified': False,
        'resume_authorized': False, 'release_authorized': False,
    }
    return {
        'tenant_id': plan_data['tenant_id'], 'cluster_id': plan_data['cluster_id'],
        'generation': plan_data['generation'],
        'plan_sha256': plan_data['plan_sha256'],
        'handoff_fingerprint': plan_data['handoff_fingerprint'],
        'status': 'provider_handoff_not_started',
        'observed_components': [observed], 'observed_count': 0,
        'recovery': recovery,
        'provider_handoff_observed': False, 'provider_mutation_performed': False,
        'provider_handoff_verified': False, 'release_authorized': False,
        'external_successor_verified': False,
    }


def prepare(monkeypatch, *, expired=True, actor=42, readback=None, mutate=None, executions=None):
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
    from app.kubernetes.tenant import native_handoff_executor, native_handoff_readback
    if callable(readback):
        readback = readback(data)
    if callable(executions):
        executions = executions(data)
    if readback == 'zero':
        readback_receipts = [canonical_no_transfer_readback(data)]
    elif readback == 'current':
        readback_receipts = [{'plan_sha256': data['plan_sha256']}]
    elif isinstance(readback, list):
        readback_receipts = readback
    elif readback:
        readback_receipts = [readback]
    else:
        readback_receipts = []
    monkeypatch.setattr(
        native_handoff_readback, 'native_handoff_readback_history',
        lambda _: readback_receipts,
    )
    monkeypatch.setattr(
        native_handoff_executor, 'native_handoff_execution_history',
        lambda _: executions or [],
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
    with pytest.raises(ValueError, match='read-back'):
        prepare(monkeypatch, readback='current')


def test_changed_provider_inventory_blocks_restart(monkeypatch):
    def changed(data):
        return {**data, 'handoff_fingerprint': 'another-inventory'}
    with pytest.raises(ValueError, match='fingerprint|inventory changed'):
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


def test_canonical_zero_transfer_receipt_allows_only_fresh_rechecked_restart(monkeypatch):
    renewed, original, session = prepare(monkeypatch, readback='zero')
    assert renewed['plan_sha256'] != original['plan_sha256']
    assert renewed['restart_zero_transfer_readback_reverified'] is True
    assert renewed['supersedes_plan_sha256'] == original['plan_sha256']
    assert renewed['status'] == 'pending_independent_approval'
    assert renewed['release_authorized'] is False
    assert session.commits == 1


def test_zero_transfer_receipt_does_not_bypass_fresh_identity_comparison(monkeypatch):
    with pytest.raises(ValueError, match='Provider inventory changed'):
        prepare(
            monkeypatch, readback='zero',
            mutate=lambda evidence: {
                **evidence,
                'live_provider_identity': [
                    {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'uid-1', 'resource_version': '22'},
                ],
            },
        )


def test_zero_transfer_receipt_does_not_bypass_fresh_provider_uid_check(monkeypatch):
    with pytest.raises(ValueError, match='Namespace handoff coverage|Provider inventory changed'):
        prepare(
            monkeypatch, readback='zero',
            mutate=lambda evidence: {
                **evidence,
                'live_provider_identity': [
                    {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'new-uid', 'resource_version': '21'},
                ],
            },
        )


@pytest.mark.parametrize('field,value', [
    ('status', 'partial_handoff_recovery_required'),
    ('observed_count', 1),
    ('handoff_fingerprint', 'unrelated'),
    ('provider_handoff_observed', True),
    ('release_authorized', True),
])
def test_corrupt_or_transferred_receipts_never_allow_restart(monkeypatch, field, value):
    def bad_receipt(data):
        receipt = canonical_no_transfer_readback(data)
        receipt[field] = value
        return receipt

    with pytest.raises(ValueError, match='recovery review'):
        prepare(monkeypatch, readback=bad_receipt)


def test_previous_partial_observation_cannot_be_hidden_by_latest_zero(monkeypatch):
    def history(data):
        zero = canonical_no_transfer_readback(data)
        partial = {**zero, 'status': 'partial_handoff_recovery_required'}
        return [zero, partial]

    with pytest.raises(ValueError, match='recovery review'):
        prepare(monkeypatch, readback=history)


def test_any_same_plan_executor_attempt_blocks_restart_even_after_zero(monkeypatch):
    with pytest.raises(ValueError, match='execution exists'):
        prepare(
            monkeypatch, readback='zero',
            executions=lambda data: [{
                'plan_sha256': data['plan_sha256'],
                'status': 'partial_handoff_recovery_required',
            }],
        )


def test_unknown_or_incomplete_receipt_stays_fail_closed(monkeypatch):
    with pytest.raises(ValueError, match='read-back history is incomplete'):
        prepare(monkeypatch, readback={'status': 'provider_handoff_not_started'})




def test_independently_authorized_failed_before_write_can_renew_only_after_fresh_verification(monkeypatch):
    from app.kubernetes.tenant import native_no_transfer_recovery as recovery
    decision = {
        'assessment_sha256': 'a' * 64,
        'provider_proof_sha256': 'b' * 64,
        'authorized_by': 44,
    }
    monkeypatch.setattr(
        recovery, 'require_authorized_no_transfer_restart',
        lambda **_: decision,
    )
    monkeypatch.setattr(
        recovery, '_source_history',
        lambda *args: {'digest': 'c' * 64, 'executor_actor_id': 43, 'failed_event_id': 2},
    )
    monkeypatch.setattr(
        recovery, '_verify_original_provider_state',
        lambda **_: {'provider_proof_sha256': decision['provider_proof_sha256']},
    )

    def failed_attempts(original):
        return [
            {'plan_sha256': original['plan_sha256'], 'status': 'in_progress'},
            {'plan_sha256': original['plan_sha256'], 'status': 'partial_handoff_recovery_required'},
        ]

    renewed, original, session = prepare(monkeypatch, executions=failed_attempts)
    assert renewed['plan_sha256'] != original['plan_sha256']
    assert renewed['supersedes_plan_sha256'] == original['plan_sha256']
    assert renewed['no_transfer_recovery_assessment_sha256'] == 'a' * 64
    assert renewed['no_transfer_recovery_authorized_by'] == 44
    assert renewed['status'] == 'pending_independent_approval'
    assert renewed['release_authorized'] is False
    assert session.commits == 1


def test_changed_provider_proof_still_blocks_independently_authorized_restart(monkeypatch):
    from app.kubernetes.tenant import native_no_transfer_recovery as recovery
    monkeypatch.setattr(
        recovery, 'require_authorized_no_transfer_restart',
        lambda **_: {
            'assessment_sha256': 'a' * 64,
            'provider_proof_sha256': 'b' * 64,
            'authorized_by': 44,
        },
    )
    monkeypatch.setattr(recovery, '_source_history', lambda *args: {'digest': 'c' * 64})
    monkeypatch.setattr(
        recovery, '_verify_original_provider_state',
        lambda **_: {'provider_proof_sha256': 'different'},
    )
    with pytest.raises(ValueError, match='Live provider proof changed'):
        prepare(
            monkeypatch,
            executions=lambda original: [
                {'plan_sha256': original['plan_sha256'], 'status': 'in_progress'},
                {'plan_sha256': original['plan_sha256'], 'status': 'partial_handoff_recovery_required'},
            ],
        )
