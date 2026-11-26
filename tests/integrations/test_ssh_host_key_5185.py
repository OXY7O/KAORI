"""Offline canonical public host-key qualification; never SSH or credential access."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.infrastructure_automation.ssh_host_key import qualify_ed25519_host_key
from app.models.automation import AutomationHostTrustRevision

# RFC 8032 public test vector, encoded as an SSH wire-format public key.
_RAW = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
_BLOB = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + _RAW
_KEY = 'ssh-ed25519 ' + base64.b64encode(_BLOB).decode('ascii')
_DIGEST = 'sha256:' + hashlib.sha256(_BLOB).hexdigest()


def test_exact_public_key_matches_wire_digest_without_asserting_trust():
    result = qualify_ed25519_host_key(_KEY, expected_digest=_DIGEST)
    assert result is not None
    assert result.algorithm == 'ssh-ed25519'
    assert result.public_key == _KEY
    assert result.digest == _DIGEST
    assert _KEY not in repr(result)
    assert not hasattr(result, 'execution_authorized')
    assert not hasattr(result, 'ssh_trust_verified')


@pytest.mark.parametrize(
    'value',
    [
        '',
        ' ' + _KEY,
        _KEY + ' comment',
        _KEY + '\n',
        _KEY.replace(' ', '\t'),
        _KEY.replace(' ', '  '),
        _KEY.replace('ssh-ed25519', 'ssh-rsa'),
        _KEY.replace('ssh-ed25519', 'ssh-ed25519-cert-v01@openssh.com'),
        'ssh-ed25519 !!!!',
        'ssh-ed25519 ' + base64.b64encode(_BLOB + b'\x00').decode('ascii'),
        'ssh-ed25519 ' + base64.b64encode(_BLOB[:-1]).decode('ascii'),
        'ssh-ed25519 ' + 'A' * 200,
        '-----BEGIN PRIVATE KEY-----',
    ],
)
def test_invalid_or_noncanonical_public_key_is_denied(value):
    assert qualify_ed25519_host_key(value, expected_digest=_DIGEST) is None


@pytest.mark.parametrize('digest', ['', 'sha256:' + '0' * 64, _DIGEST.upper(), 'sha256:é'])
def test_missing_or_mismatched_candidate_digest_is_denied(digest):
    assert qualify_ed25519_host_key(_KEY, expected_digest=digest) is None


@pytest.mark.parametrize(
    'failure',
    [None, 'self_verification', 'missing_verifier', 'expired', 'wrong_source', 'wrong_algorithm', 'invalid_port'],
)
def test_independent_host_trust_revision_constraints(failure):
    # Isolate CHECK constraints; this does not establish FK or provenance
    # qualification, or exercise PostgreSQL row locking.
    engine = create_engine('sqlite://')
    table = AutomationHostTrustRevision.__table__
    now = datetime.now(UTC)
    values = {
        'assignment_id': 1,
        'revision_number': 2,
        'lifecycle_status': 'active',
        'host_revision': 'a' * 64,
        'reference_fingerprint': 'b' * 64,
        'address': '192.0.2.1',
        'ssh_port': 22,
        'algorithm': 'ssh-ed25519',
        'public_key': _KEY,
        'host_key_digest': _DIGEST,
        'source_kind': 'independent_console',
        'evidence_ref': 'fixture-console-evidence',
        'requested_by_user_id': 1,
        'verified_by_user_id': 2,
        'verified_at': now,
        'effective_until': now + timedelta(hours=1),
        'recorded_at': now,
        'recorded_by_user_id': 2,
    }
    if failure == 'self_verification':
        values['verified_by_user_id'] = 1
    elif failure == 'missing_verifier':
        values['verified_by_user_id'] = None
    elif failure == 'expired':
        values['effective_until'] = now - timedelta(seconds=1)
    elif failure == 'wrong_source':
        values['source_kind'] = 'tofu'
    elif failure == 'wrong_algorithm':
        values['algorithm'] = 'ssh-rsa'
    elif failure == 'invalid_port':
        values['ssh_port'] = 0
    try:
        with engine.begin() as connection:
            table.create(connection)
            if failure is None:
                connection.execute(table.insert().values(**values))
                revoked = {**values, 'revision_number': 3, 'lifecycle_status': 'revoked'}
                revoked['recorded_at'] = now + timedelta(hours=2)
                connection.execute(table.insert().values(**revoked))
            else:
                with pytest.raises(IntegrityError):
                    connection.execute(table.insert().values(**values))
    finally:
        engine.dispose()
