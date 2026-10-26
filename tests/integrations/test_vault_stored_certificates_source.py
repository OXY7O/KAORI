"""Stored-certificate Vault API reads must be bounded and source-qualified."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.integrations.secrets_management.secrets_pki.providers.vault.client import (
    VaultClient,
    VaultProviderError,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_stored_certificates import (
    MAX_STORED_CERTIFICATES,
    collect_pki_stored_certificates,
)


@pytest.fixture
def certificate():
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'private.workload.example')])
    return (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(101)
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=32))
        .sign(private_key, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
        .decode('ascii')
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('INTEGRATION_VAULT_ALLOWED_ORIGINS', 'https://vault.internal.example:8200')
    provider = VaultClient(
        endpoint='https://vault.internal.example:8200',
        role_id='observer', secret_id='not-a-real-credential',
    )
    monkeypatch.setattr(provider, 'login', lambda: 'ephemeral-token')
    return provider


def test_only_list_stored_and_read_public_certificate(client, certificate, monkeypatch):
    calls = []

    def fake_request(path, *, method='GET', token=None, payload=None):
        calls.append((path, method))
        assert token == 'ephemeral-token'
        if path == '/v1/pki/certs':
            return 200, {'data': {'keys': ['65']}}
        if path == '/v1/pki/cert/65':
            return 200, {'data': {
                'certificate': certificate,
                'private_key': 'NEVER-READ-OR-STORE',
                'issuer_id': 'private-source-id',
                'revocation_time': 1234,
            }}
        pytest.fail('Unexpected provider endpoint or privileged mutation')

    monkeypatch.setattr(client, '_request', fake_request)
    observed = collect_pki_stored_certificates(client, mount='pki')
    assert observed.complete
    assert observed.coverage == 'vault_stored_only'
    assert len(observed.certificates) == 1
    assert observed.certificates[0].serial_hex == '65'
    assert observed.certificates[0].certificate.serial_hex == '65'
    assert calls == [('/v1/pki/certs', 'LIST'), ('/v1/pki/cert/65', 'GET')]
    for secret in ('private.workload.example', 'NEVER-READ-OR-STORE', 'ephemeral-token', certificate):
        assert secret not in repr(observed)


def test_oversized_listing_fails_before_certificate_reads(client, monkeypatch):
    calls = []

    def fake_request(path, **_kwargs):
        calls.append(path)
        return 200, {'data': {'keys': [f'{i:02x}' for i in range(MAX_STORED_CERTIFICATES + 1)]}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='bounded'):
        collect_pki_stored_certificates(client, mount='pki')
    assert calls == ['/v1/pki/certs']


def test_malformed_serial_and_duplicate_listing_fail_before_detail(client, monkeypatch):
    for keys in (['ca'], ['crl'], ['../keys'], ['aa', 'aa'], ['AA'], ['a:1'], ['00:65', '65']):
        calls = []

        def fake_request(path, **_kwargs):
            calls.append(path)
            return 200, {'data': {'keys': keys}}

        monkeypatch.setattr(client, '_request', fake_request)
        with pytest.raises(VaultProviderError):
            collect_pki_stored_certificates(client, mount='pki')
        assert calls == ['/v1/pki/certs']


def test_mismatched_cert_serial_cannot_commit(client, certificate, monkeypatch):
    def fake_request(path, **_kwargs):
        if path == '/v1/pki/certs':
            return 200, {'data': {'keys': ['ab']}}
        return 200, {'data': {'certificate': certificate}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='differs'):
        collect_pki_stored_certificates(client, mount='pki')


def test_listing_denied_or_malformed_is_not_healthy_empty(client, monkeypatch):
    for result in ((403, {}), (404, {}), (200, {'data': {'keys': None}})):
        monkeypatch.setattr(client, '_request', lambda *_args, **_kwargs: result)
        with pytest.raises(VaultProviderError, match='unavailable'):
            collect_pki_stored_certificates(client, mount='pki')


def test_bad_mount_is_rejected_before_authentication(client, monkeypatch):
    monkeypatch.setattr(client, 'login', lambda: pytest.fail('Must not login for unsafe mount'))
    with pytest.raises(VaultProviderError, match='mount'):
        collect_pki_stored_certificates(client, mount='../pki')
