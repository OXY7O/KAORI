"""Non-authorizing SSH trust revision candidate correlation (#5185)."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.infrastructure_automation.host_enrollment import host_revision
from app.infrastructure_automation.ssh_trust_candidate import trust_revision_candidate_matches
from app.models.automation import (
    AutomationHostAccessBinding,
    AutomationHostAsset,
    AutomationHostTrustRevision,
    AutomationInventoryAssignment,
)

_RAW = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
_BLOB = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + _RAW
_KEY = 'ssh-ed25519 ' + base64.b64encode(_BLOB).decode('ascii')
_DIGEST = 'sha256:' + hashlib.sha256(_BLOB).hexdigest()


def _candidate(now):
    host = AutomationHostAsset(
        id='00000000-0000-4000-8000-000000000001',
        name='node',
        environment='development',
        address='192.0.2.1',
        ssh_port=22,
        lifecycle_status='registered',
        updated_at=now,
    )
    assignment = AutomationInventoryAssignment(
        id=1,
        integration_instance_id=1,
        host_id=host.id,
        host=host,
        role='worker',
        enabled=True,
        updated_at=now,
    )
    binding = AutomationHostAccessBinding(
        assignment_id=assignment.id,
        secret_representation_id=1,
        secret_version=1,
        host_revision=host_revision(assignment),
        reference_fingerprint='b' * 64,
        host_key_digest=_DIGEST,
        recorded_by_user_id=1,
        recorded_at=now,
    )
    revision = AutomationHostTrustRevision(
        assignment_id=assignment.id,
        revision_number=2,
        lifecycle_status='active',
        host_revision=binding.host_revision,
        reference_fingerprint=binding.reference_fingerprint,
        address=host.address,
        ssh_port=host.ssh_port,
        algorithm='ssh-ed25519',
        public_key=_KEY,
        host_key_digest=_DIGEST,
        source_kind='independent_console',
        evidence_ref='sha256:' + 'c' * 64,
        requested_by_user_id=3,
        verified_by_user_id=2,
        verified_at=now,
        recorded_by_user_id=2,
        recorded_at=now,
        effective_until=now + timedelta(hours=1),
    )
    return assignment, binding, revision


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('lifecycle_status', 'draft'),
        ('lifecycle_status', 'revoked'),
        ('revision_number', 0),
        ('assignment_id', 2),
        ('host_revision', 'd' * 64),
        ('reference_fingerprint', 'd' * 64),
        ('address', '192.0.2.2'),
        ('ssh_port', 2222),
        ('algorithm', 'ssh-rsa'),
        ('public_key', _KEY + ' comment'),
        ('host_key_digest', 'sha256:' + 'd' * 64),
        ('source_kind', 'tofu'),
        ('evidence_ref', 'unqualified-console-reference'),
        ('verified_by_user_id', None),
        ('verified_by_user_id', 3),
        ('verified_by_user_id', 1),
        ('recorded_by_user_id', 3),
        ('verified_at', None),
    ],
)
def test_revision_mismatch_denied(field, value):
    now = datetime.now(UTC)
    assignment, binding, revision = _candidate(now)
    setattr(revision, field, value)
    assert not trust_revision_candidate_matches(latest=revision, assignment=assignment, binding=binding, now=now)


def test_current_shape_only_and_no_fallback():
    now = datetime.now(UTC)
    assignment, binding, revision = _candidate(now)
    assert trust_revision_candidate_matches(latest=revision, assignment=assignment, binding=binding, now=now)
    assert not trust_revision_candidate_matches(latest=None, assignment=assignment, binding=binding, now=now)
    assert not trust_revision_candidate_matches(latest=revision, assignment=assignment, binding=None, now=now)
    assert not trust_revision_candidate_matches(
        latest=revision, assignment=assignment, binding=binding, now=revision.effective_until
    )
    revision.lifecycle_status = 'revoked'
    assert not trust_revision_candidate_matches(latest=revision, assignment=assignment, binding=binding, now=now)


@pytest.mark.parametrize('drift', ['address', 'port', 'role', 'disabled', 'retired', 'reference'])
def test_current_candidate_drift_denied(drift):
    now = datetime.now(UTC)
    assignment, binding, revision = _candidate(now)
    if drift == 'address':
        assignment.host.address = '192.0.2.3'
    elif drift == 'port':
        assignment.host.ssh_port = 2222
    elif drift == 'role':
        assignment.role = 'control_plane'
    elif drift == 'disabled':
        assignment.enabled = False
    elif drift == 'retired':
        assignment.host.lifecycle_status = 'retired'
    else:
        binding.reference_fingerprint = 'e' * 64
    assert not trust_revision_candidate_matches(latest=revision, assignment=assignment, binding=binding, now=now)


def test_future_or_naive_clock_denied():
    now = datetime.now(UTC)
    assignment, binding, revision = _candidate(now)
    assert not trust_revision_candidate_matches(
        latest=revision, assignment=assignment, binding=binding, now=now - timedelta(seconds=1)
    )
    assert not trust_revision_candidate_matches(
        latest=revision, assignment=assignment, binding=binding, now=now.replace(tzinfo=None)
    )
