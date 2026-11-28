"""Native exact version transport regression; no real token or provider."""

import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.access.scope_policy import CredentialIssuerScope
from app.infrastructure_automation import ephemeral_ssh
from app.infrastructure_automation import native_credential_reader as service
from app.infrastructure_automation.remote_preflight_facts import RemoteFactsTarget, normalize_remote_facts
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    CredentialVersionSelector,
    ProviderCredentialVersionSelector,
)
from app.integrations.secrets_management.secrets_pki.providers.issuer_transit import TransitIssuerBinding
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPTransport, SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.ssh_credential_material import SCHEMA
from app.secrets_pki.issuer_authority import DeploymentAuthority, deployment_identity_ref

_PATH = 'fixture/ssh'
_CREATED = '2026-11-27T00:00:00+00:00'
_TOKEN = 'fixture-only-not-a-real-token'


def _selection(provider):
    now = datetime.now(UTC)
    transit = TransitIssuerBinding(provider, 'https://fixture.invalid', 'cluster-fixture', '', 'transit', 'issuer', 1, 'a' * 64)
    scope = CredentialIssuerScope(1, provider, '', 'kv', 'b' * 64)
    scope = replace(scope, deployment_ref=deployment_identity_ref(scope, transit))
    deployment = DeploymentAuthority(scope, transit, 1, 2, now - timedelta(minutes=1), now + timedelta(minutes=10), 'c' * 64)
    selector = ProviderCredentialVersionSelector(
        provider, scope.deployment_ref, 2, '00000000-0000-4000-8000-000000000001', 1,
        CredentialVersionSelector(1, '', 'kv', sha256(_PATH.encode()).hexdigest(), 7, _CREATED),
    )
    return service.NativeCredentialSelection(selector, deployment, _PATH), now + timedelta(minutes=4)


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


def _response():
    return {
        'data': {
            'data': {
                'schema': SCHEMA,
                'username': 'fixture',
                'private_key': Ed25519PrivateKey.generate().private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()
                ).decode('ascii'),
            },
            'metadata': {'created_time': _CREATED, 'deletion_time': '', 'destroyed': False, 'version': 7},
        }
    }


class _Transport:
    def __init__(self, selection, drift):
        self.selection = selection
        self.drift = drift
        self.calls = []
        self.metadata_reads = 0

    def _request(self, path, *, method='GET', token=None, payload=None, kv2_version=None):
        self.calls.append((path, method, kv2_version))
        metadata, data, policy = service._paths(self.selection)
        if path == '/v1/sys/health':
            return 200, {
                'initialized': True, 'sealed': self.drift == 'sealed', 'standby': False,
                'cluster_id': 'other' if self.drift == 'cluster' else 'cluster-fixture',
            }
        if path == '/v1/auth/token/lookup-self':
            return 200, {'data': {
                'policies': ['root'] if self.drift == 'root' else [policy],
                'identity_policies': ['other'] if self.drift == 'identity' else [],
                'renewable': self.drift == 'renewable',
                'ttl': 3600 if self.drift == 'ttl' else 30,
            }}
        if path == '/v1/sys/capabilities-self':
            assert method == 'POST' and payload == {'paths': [metadata, data]}
            return 200, {'data': {
                metadata: ['read'], data: ['read', 'update'] if self.drift == 'capability' else ['read'],
            }}
        if path == '/v1/' + metadata:
            self.metadata_reads += 1
            result = _metadata()
            if self.drift == 'stale' or (self.drift == 'rotated' and self.metadata_reads > 1):
                result['data']['current_version'] = 8
            if self.drift == 'deleted':
                result['data']['versions']['7']['deletion_time'] = _CREATED
            return 200, result
        if path == '/v1/' + data:
            assert method == 'GET' and kv2_version == 7
            response = _response()
            if self.drift == 'wrong_version':
                response['data']['metadata']['version'] = 6
            return 200, response
        pytest.fail('Unexpected provider request')


def _setup(monkeypatch, provider, drift=None):
    selection, deadline = _selection(provider)
    transport = _Transport(selection, drift)
    monkeypatch.setattr(service, '_transport', lambda binding, **kwargs: transport)
    monkeypatch.setattr(service, 'resolve_deployment_authority', lambda *args, **kwargs: selection.deployment)
    return selection, deadline, transport


@pytest.mark.parametrize('provider', ['openbao', 'vault'])
def test_exact_native_read_uses_explicit_version_and_rechecks(provider, monkeypatch):
    selection, deadline, transport = _setup(monkeypatch, provider)
    result = service._read_exact_native_ssh_credential(selection, token=_TOKEN, deadline=deadline)
    assert result.username == 'fixture'
    assert ('/v1/kv/data/fixture/ssh', 'GET', 7) in transport.calls
    assert transport.metadata_reads == 2
    assert sum(path == '/v1/sys/health' for path, _, _ in transport.calls) == 2
    assert _TOKEN not in repr(result)


@pytest.mark.parametrize('drift', ['sealed', 'cluster', 'root', 'identity', 'renewable', 'ttl', 'capability', 'stale', 'deleted'])
def test_pre_read_failures_never_fetch_material(monkeypatch, drift):
    selection, deadline, transport = _setup(monkeypatch, 'openbao', drift)
    with pytest.raises(SecretProviderError):
        service._read_exact_native_ssh_credential(selection, token=_TOKEN, deadline=deadline)
    assert not any('/data/' in path for path, _, _ in transport.calls)


@pytest.mark.parametrize('drift', ['rotated', 'wrong_version'])
def test_post_read_drift_never_returns_material(monkeypatch, drift):
    selection, deadline, transport = _setup(monkeypatch, 'openbao', drift)
    with pytest.raises(SecretProviderError):
        service._read_exact_native_ssh_credential(selection, token=_TOKEN, deadline=deadline)
    assert transport.metadata_reads == 2


def test_wrong_canonical_path_or_revoked_deployment_denies(monkeypatch):
    selection, deadline, transport = _setup(monkeypatch, 'openbao')
    with pytest.raises(SecretProviderError):
        service._read_exact_native_ssh_credential(replace(selection, path='fixture/other'), token=_TOKEN, deadline=deadline)
    monkeypatch.setattr(service, 'resolve_deployment_authority', lambda *args, **kwargs: None)
    with pytest.raises(SecretProviderError):
        service._read_exact_native_ssh_credential(selection, token=_TOKEN, deadline=deadline)
    assert transport.calls == []


@pytest.mark.parametrize('path,method,version', [
    ('/v1/kv/metadata/fixture', 'GET', 7),
    ('/v1/kv/data/fixture', 'POST', 7),
    ('/v1/kv/data/fixture', 'GET', True),
    ('/v1/kv/data/../fixture', 'GET', 7),
    ('/v1/kv/data/fixture?version=7', 'GET', 7),
])
def test_transport_rejects_non_exact_version_operation(monkeypatch, path, method, version):
    monkeypatch.setenv('FIXTURE_ORIGINS', 'https://fixture.invalid')
    transport = KV2HTTPTransport(
        endpoint='https://fixture.invalid', provider_label='Fixture',
        allowed_origins_env='FIXTURE_ORIGINS', ca_bundle_env='FIXTURE_CA',
    )
    with pytest.raises(SecretProviderError):
        transport._request(path, method=method, token=_TOKEN, kv2_version=version)


def _synthetic_target(index, material):
    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    ).decode('ascii')
    digest = 'sha256:' + sha256(base64.b64decode(public.split(' ')[1])).hexdigest()
    return ephemeral_ssh.SSHMaterialTarget(
        f'kaori-{index}', f'10.0.0.{index}', 22, public, digest, material
    )


def _synthetic_events(targets):
    facts = {
        'ansible_distribution': 'Ubuntu',
        'ansible_distribution_version': '24.04',
        'ansible_distribution_major_version': '24',
        'ansible_kernel': '6.8.0-41-generic',
        'ansible_architecture': 'x86_64',
        'ansible_pkg_mgr': 'apt',
        'ansible_python_version': '3.12.3',
        'ansible_processor_vcpus': 4,
        'ansible_memtotal_mb': 8192,
        'ansible_effective_user_id': 1000,
        'ansible_mounts': [{'mount': '/', 'size_total': 80 * 1024**3, 'size_available': 60 * 1024**3}],
        'fixture_secret_not_observed': _TOKEN,
    }
    return [
        {'event': 'runner_on_ok', 'event_data': {
            'host': target.alias, 'task_action': 'ansible.builtin.setup',
            'res': {'changed': False, 'ansible_facts': facts},
        }}
        for target in targets
    ]


@pytest.mark.parametrize('provider', ['openbao', 'vault'])
def test_mock_provider_to_ephemeral_inventory_to_synthetic_facts(provider, monkeypatch, tmp_path):
    # Exercise the actual adapter handoffs, but mock provider transport and
    # mount qualification. Never call SSH, Runner, a real provider or broker.
    monkeypatch.setattr(ephemeral_ssh, '_worker_tmpfs_root', lambda: tmp_path)
    targets = []
    for index in range(1, 4):
        selection, deadline, transport = _setup(monkeypatch, provider)
        material = service._read_exact_native_ssh_credential(selection, token=_TOKEN, deadline=deadline)
        assert transport.metadata_reads == 2
        targets.append(_synthetic_target(index, material))
    facts_targets = tuple(
        RemoteFactsTarget(target.alias, f'00000000-0000-4000-8000-{index:012d}',
                          'control_plane' if index == 1 else 'worker')
        for index, target in enumerate(targets, start=1)
    )
    with ephemeral_ssh.prepare_ephemeral_ssh(tuple(targets)) as files:
        root = files.config.parent
        assert files.inventory.read_text().splitlines() == [
            '[kaori_remote_pilot]', *[target.alias for target in facts_targets],
        ]
        for target in targets:
            loaded = serialization.load_ssh_private_key(
                (root / (target.alias + '.key')).read_bytes(), password=None
            )
            assert loaded.public_key().public_bytes_raw() == target.credential.private_key.public_key().public_bytes_raw()
        summary = normalize_remote_facts(
            facts_targets, events=_synthetic_events(facts_targets),
            stats={'ok': {target.alias: 1 for target in facts_targets}, 'changed': {}},
        ).committed_summary()
        assert len(summary['hosts']) == 3
        assert summary['full_preflight_verified'] is False
        assert summary['execution_authorized'] is False
        assert _TOKEN not in str(summary)
        assert str(root) not in str(summary)
        assert '10.0.0.' not in str(summary)
    assert not root.exists()
    assert list(tmp_path.iterdir()) == []


def test_mock_provider_rotation_prevents_complete_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(ephemeral_ssh, '_worker_tmpfs_root', lambda: pytest.fail('Incomplete bundle reached disk'))
    targets = []
    with pytest.raises(SecretProviderError):
        for index in range(1, 4):
            selection, deadline, _ = _setup(monkeypatch, 'openbao', 'rotated' if index == 2 else None)
            material = service._read_exact_native_ssh_credential(selection, token=_TOKEN, deadline=deadline)
            targets.append(_synthetic_target(index, material))
        with ephemeral_ssh.prepare_ephemeral_ssh(tuple(targets)):
            pytest.fail('Rotated credential must not yield a complete bundle')
    assert len(targets) == 1
    assert list(tmp_path.iterdir()) == []
