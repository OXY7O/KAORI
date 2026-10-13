"""#1229: source-only attempt state projection, never executable handoff.

These regressions are AUTHORED ONLY; do not execute while DevContainer
review and CI/CD gates remain held.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.kubernetes.tenant.capsule_handoff_attempt_state import (
    _event_checksum,
    project_capsule_attempt_history,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest, capsule_related_scope_sha256
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash

_ATTEMPT = '00000000-0000-4000-8000-000000000001'


def _scope():
    rows = []
    lists = [
        {'namespace': 'demo-dev', 'kind': kind, 'list_resource_version': 'list-rv', 'count': 0}
        for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')
    ]
    related_sha = capsule_related_scope_sha256(resources=rows, list_snapshots=lists)
    global_quota = {
        'status': 'observed_not_handoff_authorized',
        'served_version': 'v1beta2',
        'list_resource_version': 'global-rv',
        'resources': [],
        'count': 0,
        'blockers': [],
    }
    global_quota['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'resources': [],
        }
    )
    components = [
        {
            'kind': 'CapsuleTenant',
            'name': 'demo',
            'uid': 'cr-uid',
            'resource_version': '3',
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
            'resource_version': '9',
            'authority': 'capsule',
            'ownership': 'kaori_marker_correlated',
            'handoff': 'external_acceptance_required',
        },
    ]
    from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint

    plan = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 1,
        'provider': 'capsule',
        'requested_by': 10,
        'requested_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': handoff_fingerprint(components),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '3'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '9'},
        ],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-1011',
        'handoff_components': components,
    }
    plan['plan_sha256'] = _plan_hash(plan)
    related = {
        'status': 'read_only_related_inventory',
        'resources': rows,
        'resource_count': 0,
        'list_snapshots': lists,
        'resource_sha256': related_sha,
        'global_quota': global_quota,
    }
    return plan, related


def _event(
    plan,
    related,
    *,
    event_type='started',
    prior=None,
    attempt_id=_ATTEMPT,
    seconds=0,
    actor=30,
):
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    outcome = {
        'started': 'unknown',
        'partial': 'unknown',
        'readback_candidate': 'readback_observed',
        'recovery_reviewed': 'review_only',
    }[event_type]
    count = sum(
        item['decision']
        in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        )
        for item in worklist['items']
    )
    event = {
        'contract_version': 'capsule-handoff-attempt/v1',
        'event_type': event_type,
        'attempt_id': attempt_id,
        'sequence': prior['sequence'] + 1 if prior else 1,
        'event_at': (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(),
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'actor_user_id': 31 if event_type == 'recovery_reviewed' else actor,
        'previous_event_sha256': prior['event_sha256'] if prior else None,
        'event_sha256': None,
        'outcome': outcome,
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
    if event_type in ('readback_candidate', 'recovery_reviewed'):
        event.update(
            readback_sha256='f' * 64,
            observed_count=count,
            transferred_count=count,
        )
    if prior is not None and event_type == 'recovery_reviewed':
        for field in (
            'readback_sha256',
            'observed_count',
            'pending_count',
            'transferred_count',
            'ambiguous_count',
        ):
            event[field] = prior[field]
    event['event_sha256'] = _event_checksum(event)
    return event


def _projection(plan, related, events):
    return project_capsule_attempt_history(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        events=events,
    )


def test_empty_history_is_not_permission_to_start_or_run_any_provider_operation():
    plan, related = _scope()
    state = _projection(plan, related, [])
    assert state['status'] == 'no_attempt_observed_not_authorized'
    assert state['event_count'] == 0
    assert state['resume_authorized'] is False
    assert state['provider_execution_admitted'] is False
    assert state['release_authorized'] is False


def test_started_crash_or_timeout_always_requires_manual_recovery():
    plan, related = _scope()
    started = _event(plan, related)
    result = _projection(plan, related, [started])
    assert result['status'] == 'started_outcome_unknown_recovery_required'
    assert result['provider_handoff_verified'] is False
    assert result['auto_retry_authorized'] is False
    assert result['readback_authoritative_verified'] is False


def test_partial_and_independent_reviewer_still_cannot_retry():
    plan, related = _scope()
    started = _event(plan, related)
    partial = _event(plan, related, event_type='partial', prior=started, seconds=1)
    result = _projection(plan, related, [started, partial])
    assert result['status'] == 'partial_handoff_recovery_required'
    review = _event(plan, related, event_type='recovery_reviewed', prior=partial, seconds=2)
    approved = _projection(plan, related, [started, partial, review])
    assert approved['status'] == 'manual_review_recorded_no_retry_granted'
    assert approved['resume_authorized'] is False
    assert approved['auto_retry_authorized'] is False


def test_claimed_complete_readback_is_not_authoritative_or_released():
    plan, related = _scope()
    started = _event(plan, related)
    readback = _event(
        plan,
        related,
        event_type='readback_candidate',
        prior=started,
        seconds=1,
    )
    review = _event(
        plan,
        related,
        event_type='recovery_reviewed',
        prior=readback,
        seconds=2,
    )
    projection = _projection(plan, related, [started, readback])
    assert projection['status'] == 'readback_claim_requires_independent_provider_verification'
    assert projection['readback_claim_sha256'] == 'f' * 64
    assert projection['provider_handoff_verified'] is False
    assert projection['readback_authoritative_verified'] is False
    assert _projection(plan, related, [started, readback, review])['release_authorized'] is False


@pytest.mark.parametrize(
    'mutator',
    [
        lambda events: events[0].update(plan_sha256='a' * 64),
        lambda events: events[0].update(handoff_fingerprint='f' * 64),
        lambda events: events[0].update(actor_user_id=31),
        lambda events: events[0].update(tenant_id='foreign'),
        lambda events: events[0].update(outcome='readback_observed'),
        lambda events: events[0].update(provider_handoff_verified=True),
        lambda events: events[0].update(event_type='provider_handoff_verified'),
        lambda events: events[0].update(secret='private-credential-value'),
        lambda events: events[0].update(sequence=0),
        lambda events: events[0].update(event_at='2026-10-11'),
        lambda events: events[0].update(event_sha256='c' * 64),
    ],
)
def test_tampered_receipts_unknown_authorization_or_secrets_fail_closed(mutator):
    plan, related = _scope()
    events = [_event(plan, related)]
    mutator(events)
    with pytest.raises((ValueError, TypeError)):
        _projection(plan, related, events)


def test_replay_fork_and_monotonic_order_are_rejected():
    plan, related = _scope()
    started = _event(plan, related)
    partial = _event(plan, related, event_type='partial', prior=started, seconds=2)
    valid = _projection(plan, related, [started, partial])
    assert valid['event_count'] == 2
    corrupt = deepcopy(partial)
    corrupt['attempt_id'] = '00000000-0000-4000-8000-000000000002'
    corrupt['event_sha256'] = _event_checksum(corrupt)
    with pytest.raises(ValueError):
        _projection(plan, related, [started, corrupt])
    replay = deepcopy(partial)
    replay['previous_event_sha256'] = '1' * 64
    replay['event_sha256'] = _event_checksum(replay)
    with pytest.raises(ValueError):
        _projection(plan, related, [started, replay])
    badtime = deepcopy(partial)
    badtime['event_at'] = started['event_at']
    badtime['event_sha256'] = _event_checksum(badtime)
    with pytest.raises(ValueError):
        _projection(plan, related, [started, badtime])


def test_recovery_must_have_a_different_actor_and_no_second_started_event():
    plan, related = _scope()
    started = _event(plan, related)
    partial = _event(plan, related, event_type='partial', prior=started, seconds=1)
    review = _event(plan, related, event_type='recovery_reviewed', prior=partial, seconds=2)
    review['actor_user_id'] = 30
    review['event_sha256'] = _event_checksum(review)
    with pytest.raises(ValueError):
        _projection(plan, related, [started, partial, review])
    another_started = _event(plan, related, prior=started, seconds=1)
    with pytest.raises(ValueError):
        _projection(plan, related, [started, another_started])


def test_source_sha_drift_and_unapproved_worklist_do_not_validate_old_receipts():
    plan, related = _scope()
    started = _event(plan, related)
    related['list_snapshots'][0]['list_resource_version'] = 'changed'
    with pytest.raises(ValueError):
        _projection(plan, related, [started])
    plan, related = _scope()
    started = _event(plan, related)
    plan['generation'] = 2
    with pytest.raises(ValueError):
        _projection(plan, related, [started])
