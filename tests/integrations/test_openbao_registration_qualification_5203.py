"""Local OpenBao candidate observation; no native writes or runtime admission."""

from dataclasses import replace

import pytest

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.openbao import qualification

_CLUSTER = '4f6db34e-2042-4f0c-a385-a0d39582acb8'
_TARGET = qualification.OpenBaoQualificationTarget(
    ownership='external',
    endpoint='https://bao.example.invalid:8200',
    cluster_id=_CLUSTER,
    kv_mount='fixture-kv',
    auth_mount='fixture-approle',
    audit_mount='fixture-audit',
)
_TOKEN = 'fixture-inspection-token'


@pytest.fixture
def provider(monkeypatch):
    calls = []
    health = {
        'initialized': True,
        'sealed': False,
        'standby': False,
        'version': '2.7.3',
        'cluster_id': _CLUSTER,
    }
    replies = {
        '/v1/sys/health': (200, health),
        '/v1/auth/token/lookup-self': (200, {'data': {'policies': ['inspect'], 'ttl': 300}}),
        '/v1/sys/mounts': (200, {'data': {'fixture-kv/': {'type': 'kv', 'options': {'version': '2'}}}}),
        '/v1/sys/auth': (200, {'data': {'fixture-approle/': {'type': 'approle'}}}),
        '/v1/sys/audit': (200, {'data': {'fixture-audit/': {'type': 'file', 'options': {'log_raw': 'false'}}}}),
    }

    def request(_self, path, *, method='GET', token=None):
        assert method == 'GET'
        assert token == (None if path == '/v1/sys/health' else _TOKEN)
        calls.append(path)
        return replies[path]

    monkeypatch.setenv('INTEGRATION_OPENBAO_ALLOWED_ORIGINS', _TARGET.endpoint)
    monkeypatch.setenv('INTEGRATION_OPENBAO_CA_BUNDLE', '/fixture/ca.pem')
    monkeypatch.setattr(qualification.KV2HTTPTransport, '_request', request)
    return replies, calls


def test_exact_candidate_uses_only_read_metadata_and_rechecks_cluster(provider):
    _replies, calls = provider
    result = qualification.inspect_registration_candidate(_TARGET, token=_TOKEN)
    assert result.version == '2.7.3'
    assert len(result.evidence_ref) == 64
    assert _TOKEN not in repr(result)
    assert calls == [
        '/v1/sys/health',
        '/v1/auth/token/lookup-self',
        '/v1/sys/mounts',
        '/v1/sys/auth',
        '/v1/sys/audit',
        '/v1/sys/health',
        '/v1/auth/token/lookup-self',
    ]


@pytest.mark.parametrize(
    ('path', 'body'),
    [
        ('/v1/sys/health', {'initialized': True, 'sealed': False, 'standby': False, 'version': '2.7.3'}),
        ('/v1/auth/token/lookup-self', {'data': {'policies': ['root'], 'ttl': 300}}),
        ('/v1/auth/token/lookup-self', {'data': {'policies': ['inspect'], 'ttl': 3601}}),
        ('/v1/sys/mounts', {'data': {'other/': {'type': 'kv', 'options': {'version': '2'}}}}),
        ('/v1/sys/auth', {'data': {'fixture-approle/': {'type': 'userpass'}}}),
        ('/v1/sys/audit', {'data': {'fixture-audit/': {'type': 'file', 'options': {'log_raw': 'true'}}}}),
        ('/v1/sys/audit', {'data': {'fixture-audit/': {'type': [], 'options': {}}}}),
    ],
)
def test_unqualified_native_metadata_blocks_candidate(provider, path, body):
    replies, _calls = provider
    replies[path] = (200, body)
    with pytest.raises(SecretProviderError):
        qualification.inspect_registration_candidate(_TARGET, token=_TOKEN)


@pytest.mark.parametrize('change', [{'kv_mount': 'fixture-kv/'}, {'ownership': 'internal'}, {'cluster_id': 'invalid'}])
def test_malformed_target_fails_before_provider_io(provider, change):
    _replies, calls = provider
    with pytest.raises(SecretProviderError):
        qualification.inspect_registration_candidate(replace(_TARGET, **change), token=_TOKEN)
    assert not calls


def test_second_health_read_rejects_cluster_drift(provider, monkeypatch):
    original = qualification.KV2HTTPTransport._request
    health_reads = 0

    def changed(self, path, **kwargs):
        nonlocal health_reads
        code, body = original(self, path, **kwargs)
        if path == '/v1/sys/health':
            health_reads += 1
            if health_reads == 2:
                body = {**body, 'cluster_id': 'foreign'}
        return code, body

    monkeypatch.setattr(qualification.KV2HTTPTransport, '_request', changed)
    with pytest.raises(SecretProviderError):
        qualification.inspect_registration_candidate(_TARGET, token=_TOKEN)
