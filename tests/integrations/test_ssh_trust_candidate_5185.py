"""Non-authorizing SSH trust revision candidate correlation (#5185)."""

import base64
import hashlib
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.infrastructure_automation import ssh_trust_authority, ssh_trust_lifecycle
from app.infrastructure_automation.host_enrollment import host_revision
from app.infrastructure_automation.ssh_trust_candidate import trust_revision_candidate_matches
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import canonical_statement
from app.models.automation import (
    AutomationHostAccessBinding,
    AutomationHostAsset,
    AutomationHostTrustRevision,
    AutomationInventoryAssignment,
)
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy

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


@pytest.fixture
def console_store(monkeypatch):
    now = datetime.now(UTC)
    assignment, binding, revision = _candidate(now)
    target = ssh_trust_authority.console_target(
        assignment, binding, revision_number=2, requester_id=3, verifier_id=2
    )
    assert target is not None
    root = Ed25519PrivateKey.generate()
    payload = {
        'schema': 'kaori.automation.ssh_console_evidence.v1',
        'state': 'active',
        'target': asdict(target),
        'source_kind': 'independent_console',
        'console_asset_ref': 'c' * 64,
        'public_key': _KEY,
        'verified_at': now.isoformat(),
        'expires_at': revision.effective_until.isoformat(),
    }

    def envelope(fields, signer=root):
        return canonical_statement({'payload': fields, 'signature': signer.sign(canonical_statement(fields)).hex()})

    name = ssh_trust_authority.console_evidence_name(target)
    files = {
        'root.pub': root.public_key().public_bytes_raw().hex().encode('ascii'),
        name: envelope(payload),
    }
    monkeypatch.setattr(ssh_trust_authority, '_read_console_file', files.get)
    revision.evidence_ref = 'sha256:' + hashlib.sha256(files[name]).hexdigest()
    return now, assignment, binding, revision, target, files, name, payload, envelope


def test_console_evidence_exact_signature_and_current_revocation(console_store):
    now, _, _, revision, target, files, name, payload, envelope = console_store
    result = ssh_trust_authority.resolve_console_evidence(target, now=now)
    assert result is not None
    assert result.public_key == _KEY
    assert result.evidence_ref == revision.evidence_ref
    files[name] = envelope(payload, Ed25519PrivateKey.generate())
    assert ssh_trust_authority.resolve_console_evidence(target, now=now) is None
    files[name] = envelope(payload | {'state': 'revoked'})
    assert ssh_trust_authority.resolve_console_evidence(target, now=now) is None
    del files[name]
    assert ssh_trust_authority.resolve_console_evidence(target, now=now) is None


@pytest.mark.parametrize(
    'changes',
    [
        {'source_kind': 'tofu'},
        {'console_asset_ref': 'unqualified'},
        {'public_key': _KEY + ' comment'},
        {'extra': 'unrecognized'},
        {'verified_at': '2099-01-01T00:00:00+00:00'},
        {'expires_at': '2099-01-01T00:00:00+00:00'},
    ],
)
def test_signed_console_artifact_cannot_override_qualified_shape(console_store, changes):
    now, _, _, _, target, files, name, payload, envelope = console_store
    files[name] = envelope(payload | changes)
    assert ssh_trust_authority.resolve_console_evidence(target, now=now) is None


@pytest.mark.parametrize(
    'changes',
    [
        {'assignment_id': 9},
        {'connection_id': 9},
        {'ssh_port': 2222},
        {'host_revision': 'd' * 64},
        {'reference_fingerprint': 'd' * 64},
        {'revision_number': 3},
        {'verified_by_user_id': 9},
    ],
)
def test_console_proof_cannot_be_transferred(console_store, changes):
    now, _, _, _, target, files, name, _, _ = console_store
    changed = replace(target, **changes)
    files[ssh_trust_authority.console_evidence_name(changed)] = files[name]
    assert ssh_trust_authority.resolve_console_evidence(changed, now=now) is None


def test_console_trust_readback_requires_latest_revision_and_current_roles(console_store, monkeypatch):
    now, assignment, binding, revision, _, files, name, _, _ = console_store
    monkeypatch.setattr(
        ssh_trust_lifecycle, '_current_console_context', lambda *args, **kwargs: (assignment, binding, revision)
    )
    monkeypatch.setattr(ssh_trust_lifecycle, 'lock_explicit_permissions', lambda *args: True)
    # Service context is synthetic; no persisted or native trust is created.
    policy, target = ScopeAccessPolicy(), AutomationCredentialScopeTarget()
    result = ssh_trust_lifecycle.review_current_console_trust(policy, target, now=now)
    assert result is not None
    revision.lifecycle_status = 'revoked'
    assert ssh_trust_lifecycle.review_current_console_trust(policy, target, now=now) is None
    revision.lifecycle_status = 'active'
    monkeypatch.setattr(ssh_trust_lifecycle, 'lock_explicit_permissions', lambda *args: False)
    assert ssh_trust_lifecycle.review_current_console_trust(policy, target, now=now) is None
    monkeypatch.setattr(ssh_trust_lifecycle, 'lock_explicit_permissions', lambda *args: True)
    del files[name]
    assert ssh_trust_lifecycle.review_current_console_trust(policy, target, now=now) is None


def test_console_activation_review_requires_next_revision_and_independent_verifier(console_store, monkeypatch):
    now, assignment, binding, revision, _, _, _, _, _ = console_store
    # Fixture creates a signed artifact for revision 2, so require latest 1 revoked.
    revision.lifecycle_status = 'revoked'
    revision.revision_number = 1
    monkeypatch.setattr(
        ssh_trust_lifecycle, '_current_console_context', lambda *args, **kwargs: (assignment, binding, revision)
    )
    monkeypatch.setattr(ssh_trust_lifecycle, 'lock_explicit_permissions', lambda *args: True)

    def review(requester, verifier, expected):
        return ssh_trust_lifecycle.review_console_trust_activation(
            ScopeAccessPolicy(),
            AutomationCredentialScopeTarget(),
            requester_id=requester,
            verifier_id=verifier,
            expected_revision=expected,
            now=now,
        )

    assert review(3, 2, 1) is not None
    assert review(3, 2, 2) is None
    assert review(3, 3, 1) is None
    assert review(3, binding.recorded_by_user_id, 1) is None
    revision.lifecycle_status = 'active'
    assert review(3, 2, 1) is None


def test_host_cannot_sign_its_own_console_evidence(console_store):
    now, _, _, _, target, files, name, payload, envelope = console_store
    # RFC 8032 test-vector key corresponding to the synthetic public key above.
    host_signer = Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
    )
    assert host_signer.public_key().public_bytes_raw() == _RAW
    files['root.pub'] = _RAW.hex().encode('ascii')
    files[name] = envelope(payload, host_signer)
    assert ssh_trust_authority.resolve_console_evidence(target, now=now) is None


def test_console_artifact_reader_rejects_writable_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(ssh_trust_authority, '_AUTHORITY_DIR', tmp_path)
    (tmp_path / 'root.pub').write_text('a' * 64)
    assert ssh_trust_authority._read_console_file('root.pub') is None
    assert ssh_trust_authority._read_console_file('../root.pub') is None
