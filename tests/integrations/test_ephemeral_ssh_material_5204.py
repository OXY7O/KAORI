"""Synthetic native version and transient SSH artifact tests; no network."""

from __future__ import annotations

import base64
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from stat import S_IMODE

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.infrastructure_automation import ephemeral_ssh
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    CredentialVersionSelector,
    ProviderCredentialVersionSelector,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.ssh_credential_material import (
    SCHEMA,
    qualify_exact_ssh_version,
    qualify_ssh_credential_payload,
)

_NOW = datetime(2026, 11, 28, 1, tzinfo=UTC)
_CREATED = '2026-11-27T00:00:00+00:00'


def _payload(*, encryption=None):
    return {
        'schema': SCHEMA,
        'username': 'fixture',
        'private_key': Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            encryption or serialization.NoEncryption(),
        ).decode('ascii'),
    }


def _selector(provider='openbao'):
    return ProviderCredentialVersionSelector(
        provider, 'a' * 64, 2, '00000000-0000-4000-8000-000000000001', 1,
        CredentialVersionSelector(3, '', 'kv', 'b' * 64, 7, _CREATED),
    )


def _metadata():
    return {
        'data': {
            'current_version': 7,
            'oldest_version': 7,
            'max_versions': 10,
            'cas_required': True,
            'versions': {'7': {'created_time': _CREATED, 'deletion_time': '', 'destroyed': False}},
        }
    }


def _native_data():
    return {
        'data': {
            'data': _payload(),
            'metadata': {'created_time': _CREATED, 'deletion_time': '', 'destroyed': False, 'version': 7},
        }
    }


@pytest.mark.parametrize('provider', ['vault', 'openbao'])
def test_exact_current_native_version_and_schema(provider):
    material = qualify_exact_ssh_version(
        _selector(provider), metadata_before=_metadata(), metadata_after=_metadata(),
        data_response=_native_data(), now=_NOW,
    )
    assert material.username == 'fixture'
    assert isinstance(material.private_key, Ed25519PrivateKey)
    assert 'fixture' not in repr(material)


@pytest.mark.parametrize(
    'changes',
    [
        {'schema': 'generic'},
        {'username': 'root'},
        {'username': '-oProxyCommand'},
        {'username': 'a\nb'},
        {'password': 'fixture'},
        {'private_key': 'invalid'},
    ],
)
def test_material_schema_rejects_other_types_and_injection(changes):
    with pytest.raises(SecretProviderError, match='Exact SSH credential material'):
        qualify_ssh_credential_payload(_payload() | changes)


def test_encrypted_private_key_is_not_interactive_worker_credential():
    with pytest.raises(SecretProviderError):
        qualify_ssh_credential_payload(_payload(encryption=serialization.BestAvailableEncryption(b'fixture')))


@pytest.mark.parametrize('drift', [
    'rotated', 'destroyed', 'deleted', 'missing_deletion', 'created', 'wrong_version',
    'bool_version', 'missing_native_state', 'wrong_schema',
])
def test_native_version_drift_denies(drift):
    before, after, response = _metadata(), _metadata(), _native_data()
    if drift == 'rotated':
        after['data']['current_version'] = 8
    elif drift == 'destroyed':
        after['data']['versions']['7']['destroyed'] = True
    elif drift == 'deleted':
        before['data']['versions']['7']['deletion_time'] = _CREATED
        after['data']['versions']['7']['deletion_time'] = _CREATED
    elif drift == 'missing_deletion':
        del before['data']['versions']['7']['deletion_time']
    elif drift == 'created':
        response['data']['metadata']['created_time'] = _NOW.isoformat()
    elif drift == 'wrong_version':
        response['data']['metadata']['version'] = 6
    elif drift == 'bool_version':
        response['data']['metadata']['version'] = True
    elif drift == 'missing_native_state':
        del response['data']['metadata']['destroyed']
    else:
        response['data']['data']['schema'] = 'other'
    with pytest.raises(SecretProviderError):
        qualify_exact_ssh_version(
            _selector(), metadata_before=before, metadata_after=after, data_response=response, now=_NOW
        )


def _target(index):
    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    ).decode('ascii')
    digest = 'sha256:' + sha256(base64.b64decode(public.split(' ')[1])).hexdigest()
    return ephemeral_ssh.SSHMaterialTarget(
        f'kaori-{index}', f'10.0.0.{index}', 2222 if index == 2 else 22,
        public, digest, qualify_ssh_credential_payload(_payload()),
    )


@pytest.fixture
def targets():
    return tuple(_target(index) for index in range(1, 4))


def test_private_files_exact_host_keys_and_cleanup(targets, monkeypatch, tmp_path):
    # Synthetic keys only; this test replaces the mount qualification, not
    # actual tmpfs admission. No SSH invocation or provider request.
    monkeypatch.setattr(ephemeral_ssh, '_worker_tmpfs_root', lambda: tmp_path)
    with ephemeral_ssh.prepare_ephemeral_ssh(targets) as files:
        root = files.config.parent
        assert S_IMODE(root.stat().st_mode) == 0o700
        assert len(list(root.iterdir())) == 5
        assert all(S_IMODE(path.stat().st_mode) == 0o600 for path in root.iterdir())
        config = files.config.read_text()
        assert 'StrictHostKeyChecking yes' in config
        assert 'GlobalKnownHostsFile /dev/null' in config
        assert 'IdentityAgent none' in config
        assert 'PasswordAuthentication no' in config
        assert 'ProxyCommand /bin/false' in config
        assert 'BEGIN OPENSSH PRIVATE KEY' not in config
        expected = [f'10.0.0.1 {targets[0].host_key}', f'[10.0.0.2]:2222 {targets[1].host_key}',
                    f'10.0.0.3 {targets[2].host_key}']
        assert files.known_hosts.read_text().splitlines() == expected
        assert files.execution_authorized is False
    assert not root.exists()
    assert list(tmp_path.iterdir()) == []


def test_cleanup_on_consumer_and_partial_write_failure(targets, monkeypatch, tmp_path):
    monkeypatch.setattr(ephemeral_ssh, '_worker_tmpfs_root', lambda: tmp_path)
    with pytest.raises(RuntimeError):
        with ephemeral_ssh.prepare_ephemeral_ssh(targets):
            raise RuntimeError('synthetic consumer failure')
    assert list(tmp_path.iterdir()) == []
    original = ephemeral_ssh._write_private_file

    def fail_second(path, content):
        if path.name == 'kaori-2.key':
            raise OSError('synthetic write failure')
        original(path, content)

    monkeypatch.setattr(ephemeral_ssh, '_write_private_file', fail_second)
    with pytest.raises(ephemeral_ssh.EphemeralSSHError):
        with ephemeral_ssh.prepare_ephemeral_ssh(targets):
            pytest.fail('Partial preparation must not yield paths')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('changes', [
    {'address': '8.8.8.8'}, {'address': '10.0.0.2'}, {'port': True},
    {'alias': 'kaori-2'}, {'alias': 'kaori-1\nHost *'}, {'host_key_digest': 'sha256:' + '0' * 64},
])
def test_target_drift_denies_before_artifact_creation(targets, monkeypatch, changes):
    monkeypatch.setattr(
        ephemeral_ssh, '_worker_tmpfs_root', lambda: pytest.fail('Unqualified target reached filesystem')
    )
    with pytest.raises(ephemeral_ssh.EphemeralSSHError):
        with ephemeral_ssh.prepare_ephemeral_ssh((replace(targets[0], **changes), *targets[1:])):
            pytest.fail('Unqualified target yielded paths')


def test_root_worker_is_denied(monkeypatch):
    monkeypatch.setattr(ephemeral_ssh.os, 'geteuid', lambda: 0)
    with pytest.raises(ephemeral_ssh.EphemeralSSHError):
        ephemeral_ssh._worker_tmpfs_root()
