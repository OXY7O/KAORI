"""Offline canonical public host-key qualification; never SSH or credential access."""

import base64
import hashlib

import pytest

from app.infrastructure_automation.ssh_host_key import qualify_ed25519_host_key

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
