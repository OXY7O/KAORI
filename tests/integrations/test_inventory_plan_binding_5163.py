"""#5163: no approved Run can be derived from matched read-only evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.infrastructure_automation.kubernetes.inventory_plan_binding import assess_inventory_bound_plan_review

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
SHA = 'a' * 40
EE = 'sha256:' + 'b' * 64


def _evidence():
    inventory = {
        'schema_version': 1,
        'status': 'review_only',
        'fingerprint': 'c' * 64,
        'host_count': 3,
        'control_plane_count': 1,
        'worker_count': 2,
        'execution_authorized': False,
    }
    access = {
        'schema_version': 1,
        'state': 'references_recorded',
        'fingerprint': 'd' * 64,
        'credential_reference_recorded': True,
        'host_key_reference_recorded': True,
        'ssh_trust_verified': False,
        'privileged_identity_verified': False,
        'execution_authorized': False,
    }
    plan = {
        'schema_version': 1,
        'status': 'requires_independent_approval',
        'plan_fingerprint': 'e' * 64,
        'connection_id': 17,
        'inventory_fingerprint': inventory['fingerprint'],
        'host_access_fingerprint': access['fingerprint'],
        'source_sha': SHA,
        'execution_environment_digest': EE,
        'expires_at': (NOW + timedelta(minutes=10)).isoformat(),
        'approval_status': 'not_requested',
        'execution_status': 'blocked',
        'mutation_authorized': False,
    }
    return inventory, access, plan


def _evaluate(inventory=None, access=None, plan=None, **changes):
    own_inventory, own_access, own_plan = _evidence()
    params = {
        'connection_id': 17,
        'source_sha': SHA,
        'execution_environment_digest': EE,
        'inventory_evidence': own_inventory if inventory is None else inventory,
        'access_evidence': own_access if access is None else access,
        'plan_evidence': own_plan if plan is None else plan,
        'now': NOW,
    }
    params.update(changes)
    return assess_inventory_bound_plan_review(**params)


def test_exact_snapshots_only_qualify_sanitized_review_material():
    result = _evaluate()
    assert result.state == 'review_material_only'
    assert len(result.fingerprint or '') == 64
    assert result.execution_authorized is False
    summary = result.committed_summary()
    assert summary['execution_authorized'] is False
    assert summary['reason_code'] == 'INDEPENDENT_ADMISSION_REQUIRED'
    assert not any(word in str(summary) for word in ('10.0.', 'ssh', 'private', 'secret'))


@pytest.mark.parametrize(
    ('field', 'value', 'reason'),
    [
        ('connection_id', 0, 'CONNECTION_ID_UNQUALIFIED'),
        ('connection_id', True, 'CONNECTION_ID_UNQUALIFIED'),
        ('source_sha', 'latest', 'SOURCE_REVISION_UNQUALIFIED'),
        ('execution_environment_digest', 'mutable', 'EXECUTION_ENVIRONMENT_UNQUALIFIED'),
        ('now', datetime(2026, 11, 23), 'CLOCK_UNQUALIFIED'),
        ('inventory_evidence', {}, 'INVENTORY_EVIDENCE_UNQUALIFIED'),
        ('access_evidence', {}, 'HOST_ACCESS_EVIDENCE_UNQUALIFIED'),
        ('plan_evidence', {}, 'PLAN_EVIDENCE_MISMATCH'),
    ],
)
def test_unqualified_inputs_block(field, value, reason):
    result = _evaluate(**{field: value})
    assert result.state == 'blocked'
    assert result.reason_code == reason
    assert result.fingerprint is None


@pytest.mark.parametrize(
    ('which', 'field', 'value', 'reason'),
    [
        ('inventory', 'fingerprint', 'malformed', 'INVENTORY_EVIDENCE_UNQUALIFIED'),
        ('inventory', 'execution_authorized', True, 'INVENTORY_EVIDENCE_UNQUALIFIED'),
        ('inventory', 'host_count', 4, 'INVENTORY_EVIDENCE_UNQUALIFIED'),
        ('access', 'state', 'approved', 'HOST_ACCESS_EVIDENCE_UNQUALIFIED'),
        ('access', 'credential_reference_recorded', False, 'HOST_ACCESS_EVIDENCE_UNQUALIFIED'),
        ('access', 'host_key_reference_recorded', False, 'HOST_ACCESS_EVIDENCE_UNQUALIFIED'),
        ('access', 'ssh_trust_verified', True, 'HOST_ACCESS_EVIDENCE_UNQUALIFIED'),
        ('access', 'execution_authorized', True, 'HOST_ACCESS_EVIDENCE_UNQUALIFIED'),
        ('plan', 'inventory_fingerprint', 'f' * 64, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'host_access_fingerprint', 'f' * 64, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'connection_id', 18, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'connection_id', True, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'source_sha', 'f' * 40, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'execution_environment_digest', 'sha256:' + 'f' * 64, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'approval_status', 'approved', 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'mutation_authorized', True, 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'execution_status', 'succeeded', 'PLAN_EVIDENCE_MISMATCH'),
        ('plan', 'expires_at', 'not-a-time', 'PLAN_EVIDENCE_EXPIRED'),
    ],
)
def test_conflicting_evidence_is_never_inferred_as_approval(which, field, value, reason):
    i, a, p = _evidence()
    target = {'inventory': i, 'access': a, 'plan': p}[which]
    target[field] = value
    result = _evaluate(inventory=i, access=a, plan=p)
    assert result.state == 'blocked'
    assert result.reason_code == reason


def test_expired_plan_and_new_access_version_invalidate_fingerprint():
    i, a, p = _evidence()
    result = _evaluate(inventory=i, access=a, plan=p)
    assert result.state == 'review_material_only'
    a2 = deepcopy(a)
    a2['fingerprint'] = 'f' * 64
    assert _evaluate(inventory=i, access=a2, plan=p).reason_code == 'PLAN_EVIDENCE_MISMATCH'
    updated_plan = deepcopy(p)
    updated_plan['host_access_fingerprint'] = a2['fingerprint']
    assert _evaluate(inventory=i, access=a2, plan=updated_plan).fingerprint != result.fingerprint
    p['expires_at'] = NOW.isoformat()
    assert _evaluate(inventory=i, access=a, plan=p).reason_code == 'PLAN_EVIDENCE_EXPIRED'


def test_missing_binding_or_reused_access_fingerprint_is_blocked():
    inventory, access, plan = _evidence()
    for missing_key in ('connection_id', 'host_access_fingerprint'):
        missing = deepcopy(plan)
        missing.pop(missing_key)
        assert _evaluate(inventory=inventory, access=access, plan=missing).reason_code == 'PLAN_EVIDENCE_MISMATCH'

    another_access = deepcopy(access)
    another_access['fingerprint'] = 'f' * 64
    assert _evaluate(inventory=inventory, access=another_access, plan=plan).reason_code == 'PLAN_EVIDENCE_MISMATCH'
