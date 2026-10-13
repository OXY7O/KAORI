"""Capsule SQL AuditEvent history & interrupted recovery: tests authored, NOT run.

HOLD: no pytest, migration, CI/CD, provider dry-run, Kubernetes PATCH or UAT.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_handoff_persistence_review as store
from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum
from app.kubernetes.tenant.capsule_handoff_persisted_recovery import (
    review_capsule_persisted_recovery_case,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint

_ATTEMPT = '00000000-0000-4000-8000-000000000001'
_TARGET = 'kubernetes_tenant_release_capsule_handoff_execution'
_ACTIONS = {
    'started': 'tenant.release.capsule_handoff_started',
    'partial': 'tenant.release.capsule_handoff_partial',
    'readback_candidate': 'tenant.release.capsule_handoff_readback_candidate',
    'recovery_reviewed': 'tenant.release.capsule_handoff_recovery_reviewed',
}


def _fixtures():
    lists = [
        {'namespace': 'demo-dev', 'kind': kind, 'list_resource_version': 'list-rv', 'count': 0}
        for kind in ('LimitRange', 'ResourceQuota', 'RoleBinding')
    ]
    related_sha = _digest({'resources': [], 'lists': lists})
    global_quota = {
        'status': 'observed_not_handoff_authorized',
        'served_version': 'v1beta2',
        'list_resource_version': 'grq-rv',
        'resources': [],
        'count': 0,
        'blockers': [],
    }
    global_quota['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'list_resource_version': 'grq-rv',
            'resources': [],
        }
    )
    components = [
        {
            'kind': 'CapsuleTenant',
            'name': 'demo',
            'uid': 'cr-uid',
            'resource_version': '5',
            'authority': 'capsule',
            'ownership': 'external_or_unattributed',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': 'a' * 64,
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '0',
            'capsule_shared_quota_sha256': global_quota['scope_sha256'],
            'capsule_rbac_lineage_sha256': 'b' * 64,
        },
        {
            'kind': 'Namespace',
            'name': 'demo-dev',
            'namespace': 'demo-dev',
            'uid': 'ns-uid',
            'resource_version': '19',
            'authority': 'capsule',
            'ownership': 'kaori_marker_correlated',
            'handoff': 'external_acceptance_required',
        },
    ]
    plan = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 1,
        'provider': 'capsule',
        'requested_by': 10,
        'requested_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': handoff_fingerprint(components),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '5'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '19'},
        ],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-1011',
        'handoff_components': components,
    }
    plan['plan_sha256'] = _plan_hash(plan)
    related = {
        'status': 'read_only_related_inventory',
        'resources': [],
        'resource_count': 0,
        'list_snapshots': lists,
        'resource_sha256': related_sha,
        'global_quota': global_quota,
    }
    return plan, related


def _event(plan, related, *, event_type='started', prior=None, elapsed=0):
    count = sum(
        item['decision']
        in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        )
        for item in build_capsule_handoff_worklist(plan=plan, related=related)['items']
    )
    event = {
        'contract_version': 'capsule-handoff-attempt/v1',
        'event_type': event_type,
        'attempt_id': _ATTEMPT,
        'sequence': prior['sequence'] + 1 if prior else 1,
        'event_at': (datetime.now(UTC) - timedelta(seconds=30 - elapsed)).isoformat(),
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': build_capsule_handoff_worklist(
            plan=plan,
            related=related,
        )['inventory_sha256'],
        'actor_user_id': 31 if event_type == 'recovery_reviewed' else 30,
        'previous_event_sha256': prior['event_sha256'] if prior else None,
        'event_sha256': None,
        'outcome': {
            'started': 'unknown',
            'partial': 'unknown',
            'readback_candidate': 'readback_observed',
            'recovery_reviewed': 'review_only',
        }[event_type],
        'readback_sha256': None,
        'expected_count': count,
        'observed_count': 0,
        'pending_count': 0,
        'transferred_count': 0,
        'ambiguous_count': 0,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'resume_authorized': False,
        'auto_retry_authorized': False,
        'secret_material_persisted': False,
    }
    if event_type == 'readback_candidate':
        event.update(readback_sha256='f' * 64, observed_count=count, pending_count=count)
    if event_type == 'recovery_reviewed' and prior is not None:
        for key in (
            'readback_sha256',
            'observed_count',
            'pending_count',
            'transferred_count',
            'ambiguous_count',
        ):
            event[key] = prior[key]
    event['event_sha256'] = _event_checksum(event)
    return event


def _row(event, *, record_id=100, delay=1):
    return {
        'id': record_id,
        'target_type': _TARGET,
        'target_id': 'tenant-1',
        'actor_user_id': event['actor_user_id'],
        'action': _ACTIONS[event['event_type']],
        'created_at': datetime.fromisoformat(event['event_at']) + timedelta(seconds=delay),
        'metadata_json': event,
    }


def _review(plan, related, rows, readback=None):
    return review_capsule_persisted_recovery_case(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        committed_rows=rows,
        readback_candidate=readback,
    )


def test_empty_committed_stream_never_claims_trusted_persistence_or_provider_authority():
    plan, related = _fixtures()
    result = store.inspect_capsule_persistence_snapshot(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=[],
    )
    assert result['persistence_status'] == 'no_attempt_observed_storage_guarantees_missing'
    assert result['audit_record_count'] == 0
    assert result['database_write_once_enforced'] is False
    assert result['transactional_single_attempt_guaranteed'] is False
    assert result['append_authorized'] is False
    assert result['provider_execution_admitted'] is False
    docket = _review(plan, related, [])
    assert docket['status'] == 'no_attempt_no_execution_authority'
    assert docket['auto_retry_authorized'] is False


def test_started_crash_requires_recovery_and_blocks_followup_attempt():
    plan, related = _fixtures()
    started = _event(plan, related)
    snapshot = store.inspect_capsule_persistence_snapshot(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=[_row(started)],
    )
    assert snapshot['status'] == 'started_outcome_unknown_recovery_required'
    assert snapshot['new_attempt_blocked_by_history'] is True
    case = _review(plan, related, [_row(started)])
    assert case['status'] == 'unknown_provider_outcome_quarantined'
    assert 'provider_outcome_unknown_manual_recovery_required' in case['blockers']
    assert case['resume_authorized'] is False


def test_review_of_a_proposed_start_never_grants_an_sql_insert():
    plan, related = _fixtures()
    start = _event(plan, related)
    result = store.review_capsule_audit_append_candidate(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        committed_rows=[],
        candidate_event=start,
    )
    assert result['expected_event_count'] == 1
    assert result['append_authorized'] is False
    assert result['trusted_audit_persistence_verified'] is False
    assert result['prewrite_audit_commit_barrier_proven'] is False


def test_proposed_followup_must_match_exact_prior_committed_event():
    plan, related = _fixtures()
    start = _event(plan, related)
    part = _event(plan, related, event_type='partial', prior=start, elapsed=4)
    result = store.review_capsule_audit_append_candidate(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        committed_rows=[_row(start)],
        candidate_event=part,
    )
    assert result['expected_event_count'] == 2
    part['previous_event_sha256'] = 'e' * 64
    part['event_sha256'] = _event_checksum(part)
    with pytest.raises(ValueError):
        store.review_capsule_audit_append_candidate(
            tenant_id='tenant-1',
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            committed_rows=[_row(start)],
            candidate_event=part,
        )


def test_historical_different_plan_or_extra_attempt_cannot_be_filtered_out():
    plan, related = _fixtures()
    start = _event(plan, related)
    old_plan = deepcopy(start)
    old_plan['plan_sha256'] = '9' * 64
    old_plan['event_sha256'] = _event_checksum(old_plan)
    with pytest.raises(ValueError):
        store.inspect_capsule_persistence_snapshot(
            tenant_id='tenant-1',
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            rows=[_row(old_plan)],
        )
    with pytest.raises(ValueError):
        store.inspect_capsule_persistence_snapshot(
            tenant_id='tenant-1',
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            rows=[_row(start, record_id=i) for i in range(4)],
        )


def test_candidate_provider_readback_matches_claim_but_recovery_remains_blocked():
    plan, related = _fixtures()
    start = _event(plan, related)
    readback = _event(
        plan,
        related,
        event_type='readback_candidate',
        prior=start,
        elapsed=4,
    )
    rows = [_row(start, record_id=100), _row(readback, record_id=101)]
    candidate = {
        'status': 'readback_candidate_recovery_review_required',
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': build_capsule_handoff_worklist(
            plan=plan,
            related=related,
        )['inventory_sha256'],
        'readback_sha256': readback['readback_sha256'],
        'expected_count': readback['expected_count'],
        'observed_count': readback['observed_count'],
        'pending_count': readback['pending_count'],
        'transferred_count': readback['transferred_count'],
        'ambiguous_count': readback['ambiguous_count'],
        'provider_handoff_verified': False,
        'release_authorized': False,
        'provider_snapshot_authenticity_verified': False,
    }
    review = _review(plan, related, rows, candidate)
    assert review['readback_claim_correlated'] is True
    assert review['status'] == 'readback_correlated_but_unverified'
    assert review['provider_handoff_verified'] is False
    assert review['readback_authoritative_verified'] is False
    assert review['auto_retry_authorized'] is False
    tampered = dict(candidate, readback_sha256='1' * 64)
    with pytest.raises(ValueError):
        _review(plan, related, rows, tampered)


def test_started_without_outcome_never_accepts_a_forged_readback():
    plan, related = _fixtures()
    started = _event(plan, related)
    with pytest.raises(ValueError):
        _review(
            plan,
            related,
            [_row(started)],
            {
                'readback_sha256': 'e' * 64,
            },
        )


def test_truncated_query_bounded_to_four_rows_and_never_commits(monkeypatch):
    plan, related = _fixtures()

    class FakeColumn:
        def asc(self):
            return 'id asc'

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows
            self.calls = []

        def filter_by(self, **kwargs):
            self.calls.append(('filter', kwargs))
            return self

        def order_by(self, key):
            self.calls.append(('order_by', key))
            return self

        def limit(self, amount):
            self.calls.append(('limit', amount))
            return self

        def all(self):
            return self.rows

    query = FakeQuery([])
    monkeypatch.setattr(
        store,
        'AuditEvent',
        SimpleNamespace(query=query, id=FakeColumn()),
    )
    out = store.read_capsule_committed_audit_history(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
    )
    assert out['append_authorized'] is False
    assert ('filter', {'target_type': _TARGET, 'target_id': 'tenant-1'}) in query.calls
    assert ('limit', 4) in query.calls
    assert not any(name == 'commit' for name, _ in query.calls)


def test_unknown_or_deleted_sql_history_cannot_be_declared_immutable():
    plan, related = _fixtures()
    start = _event(plan, related)
    result = store.inspect_capsule_persistence_snapshot(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=[_row(start)],
    )
    assert result['historical_attempts_exhaustively_proven'] is False
    assert result['storage_durability_proven'] is False
    assert result['audit_storage_append_only_verified'] is False


def test_partial_recovery_is_quarantined_without_automatic_retry():
    plan, related = _fixtures()
    started = _event(plan, related)
    partial = _event(
        plan,
        related,
        event_type='partial',
        prior=started,
        elapsed=4,
    )
    case = _review(
        plan,
        related,
        [_row(started, record_id=100), _row(partial, record_id=101)],
    )
    assert case['status'] == 'partial_provider_outcome_quarantined'
    assert case['readback_claim_correlated'] is False
    assert case['auto_retry_authorized'] is False
    assert case['release_authorized'] is False


def test_independent_recovery_review_does_not_make_provider_claim_trusted():
    plan, related = _fixtures()
    started = _event(plan, related)
    readback = _event(
        plan,
        related,
        event_type='readback_candidate',
        prior=started,
        elapsed=4,
    )
    review = _event(
        plan,
        related,
        event_type='recovery_reviewed',
        prior=readback,
        elapsed=8,
    )
    rows = [
        _row(started, record_id=100),
        _row(readback, record_id=101),
        _row(review, record_id=102),
    ]
    case = _review(plan, related, rows)
    assert case['status'] == 'provider_readback_missing_manual_recovery'
    assert case['readback_authoritative_verified'] is False
    assert case['resume_authorized'] is False
    assert case['audit_storage_append_only_verified'] is False
    next_event = deepcopy(review)
    next_event['sequence'] = 4
    next_event['previous_event_sha256'] = review['event_sha256']
    next_event['event_sha256'] = _event_checksum(next_event)
    with pytest.raises(ValueError):
        store.review_capsule_audit_append_candidate(
            tenant_id='tenant-1',
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            committed_rows=rows,
            candidate_event=next_event,
        )
