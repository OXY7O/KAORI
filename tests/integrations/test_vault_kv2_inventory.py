from __future__ import annotations

from dataclasses import asdict

import pytest

from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient, VaultProviderError
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    MAX_SECRETS,
    _safe_metadata,
    collect_kv2_metadata,
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('INTEGRATION_VAULT_ALLOWED_ORIGINS', 'https://vault.example.internal:8200')
    return VaultClient(
        endpoint='https://vault.example.internal:8200',
        role_id='reader',
        secret_id='test-only-secret-id',
    )


def _detail(version: int = 2):
    return {
        'data': {
            'current_version': version,
            'oldest_version': 1,
            'cas_required': True,
            'max_versions': 10,
            'custom_metadata': {'confidential_account': 'do-not-store'},
            'versions': {
                '1': {'created_time': '2026-09-01T00:00:00Z', 'deletion_time': '', 'destroyed': False},
                str(version): {
                    'created_time': '2026-09-02T00:00:00Z',
                    'deletion_time': '',
                    'destroyed': False,
                },
            },
        },
        'secret': 'do-not-store',
    }


def test_collect_kv2_only_requests_metadata_and_discards_unknown_fields(client, monkeypatch):
    calls = []

    monkeypatch.setattr(client, 'login', lambda: 'transient-test-token')

    def fake_request(path, *, method='GET', token=None, payload=None):
        calls.append((path, method, token))
        assert token == 'transient-test-token'
        if path == '/v1/kv/metadata' and method == 'LIST':
            return 200, {'data': {'keys': ['service/', 'root-secret']}}
        if path == '/v1/kv/metadata/service' and method == 'LIST':
            return 200, {'data': {'keys': ['database']}}
        if method == 'GET' and path in {
            '/v1/kv/metadata/root-secret',
            '/v1/kv/metadata/service/database',
        }:
            return 200, _detail()
        raise AssertionError('Unexpected Vault operation.')

    monkeypatch.setattr(client, '_request', fake_request)
    snapshot = collect_kv2_metadata(client, mount='kv')
    assert snapshot.complete
    assert len(snapshot.records) == 2
    assert [record.path for record in snapshot.records] == ['root-secret', 'service/database']
    assert snapshot.records[0].current_version == 2
    assert snapshot.records[0].cas_required is True
    assert [item.version for item in snapshot.records[0].versions] == [1, 2]
    assert all('/metadata' in path and '/data/' not in path for path, _, _ in calls)
    safe = repr(asdict(snapshot))
    assert 'do-not-store' not in safe
    assert 'transient-test-token' not in safe
    assert 'test-only-secret-id' not in safe


@pytest.mark.parametrize('bad_mount', ['../kv', 'kv%2fsecret', 'kv//two', 'kv?x=1', 'kv\\bad', ''])
def test_rejects_unsafe_mount_before_login(client, monkeypatch, bad_mount):
    monkeypatch.setattr(client, 'login', lambda: pytest.fail('login must not happen'))
    with pytest.raises(VaultProviderError):
        collect_kv2_metadata(client, mount=bad_mount)


def test_denied_listing_never_masquerades_as_empty_inventory(client, monkeypatch):
    monkeypatch.setattr(client, 'login', lambda: 'token')
    monkeypatch.setattr(client, '_request', lambda path, **kwargs: (403, {'errors': ['secret/path']}))
    with pytest.raises(VaultProviderError) as raised:
        collect_kv2_metadata(client, mount='kv')
    assert 'secret/path' not in str(raised.value)


def test_missing_metadata_never_masquerades_as_empty_inventory(client, monkeypatch):
    monkeypatch.setattr(client, 'login', lambda: 'token')
    monkeypatch.setattr(client, '_request', lambda path, **kwargs: (404, {}))
    with pytest.raises(VaultProviderError, match='unavailable'):
        collect_kv2_metadata(client, mount='kv')


def test_fails_bounded_scan_before_fetching_oversized_collection(client, monkeypatch):
    monkeypatch.setattr(client, 'login', lambda: 'token')
    paths = []

    def fake_request(path, **kwargs):
        paths.append(path)
        return 200, {'data': {'keys': [f'secret-{index}' for index in range(MAX_SECRETS + 1)]}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='too large'):
        collect_kv2_metadata(client, mount='kv')
    assert paths == ['/v1/kv/metadata']


def test_rejects_version_evidence_above_bound_without_truncation():
    data = _detail()
    data['data']['versions'] = {
        str(index): {'created_time': '', 'deletion_time': '', 'destroyed': False} for index in range(1, 103)
    }
    with pytest.raises(VaultProviderError, match='bounded'):
        _safe_metadata(mount='kv', path='a', body=data)


def test_rejects_invalid_nested_listing_without_logging_secret_path(client, monkeypatch):
    monkeypatch.setattr(client, 'login', lambda: 'token')
    monkeypatch.setattr(
        client,
        '_request',
        lambda path, **kwargs: (
            200,
            {'data': {'keys': ['../secret']}},
        ),
    )
    with pytest.raises(VaultProviderError) as raised:
        collect_kv2_metadata(client, mount='kv')
    assert '../secret' not in str(raised.value)


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('', ()),
        ('secret', ('secret',)),
        ('secret, teams/credentials', ('secret', 'teams/credentials')),
    ],
)
def test_explicit_kv2_mount_allowlist(raw, expected):
    from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
        parse_approved_kv2_mounts,
    )

    assert parse_approved_kv2_mounts(raw) == expected


@pytest.mark.parametrize(
    'raw',
    [
        'secret,secret',
        'secret?token=x',
        '../secret',
        'secret%2fdata',
        'one,two,three,four,five,six,seven,eight,nine',
    ],
)
def test_rejects_unsafe_or_unbounded_kv2_scope(raw):
    from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
        parse_approved_kv2_mounts,
    )

    with pytest.raises(VaultProviderError):
        parse_approved_kv2_mounts(raw)


@pytest.mark.parametrize('timestamp', ['not-a-timestamp', '2026-10-22T12:00:00', 'secret/path/should-not-persist'])
def test_invalid_provider_timestamp_rejected_without_raw_value(timestamp):
    data = _detail()
    data['data']['versions']['1']['created_time'] = timestamp
    with pytest.raises(VaultProviderError) as raised:
        _safe_metadata(mount='kv', path='secret', body=data)
    assert timestamp not in str(raised.value)


@pytest.mark.parametrize('field', ['cas_required', 'destroyed'])
def test_missing_security_posture_does_not_default_to_false(field):
    data = _detail()
    if field == 'cas_required':
        data['data'].pop('cas_required')
    else:
        data['data']['versions']['1'].pop('destroyed')
    with pytest.raises(VaultProviderError):
        _safe_metadata(mount='kv', path='secret', body=data)


@pytest.mark.parametrize('bad_value', [True, 1.5, '1.5', '٢', -1, 2**31, '9' * 20])
def test_invalid_kv2_version_number_never_truncates_or_overflows(bad_value):
    data = _detail()
    data['data']['current_version'] = bad_value
    with pytest.raises(VaultProviderError, match='Invalid KV v2 version evidence'):
        _safe_metadata(mount='kv', path='secret', body=data)
