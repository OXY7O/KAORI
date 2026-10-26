from __future__ import annotations

from dataclasses import asdict
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
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    MAX_ISSUERS,
    collect_pki_public_issuers,
)

ISSUER_ID = '1ae8ce9d-2f70-0761-a465-8c9840a247a2'


@pytest.fixture
def certificate():
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Kaori Test CA')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(101)
        .not_valid_before(datetime.now(UTC) - timedelta(days=2))
        .not_valid_after(datetime.now(UTC) + timedelta(days=350))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('ca.internal.example')]), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode('ascii')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('INTEGRATION_VAULT_ALLOWED_ORIGINS', 'https://vault.internal.example:8200')
    instance = VaultClient(
        endpoint='https://vault.internal.example:8200',
        role_id='test-reader', secret_id='not-persisted',
    )
    monkeypatch.setattr(instance, 'login', lambda: 'ephemeral-token')
    return instance


def test_collects_only_public_certificate_properties(client, certificate, monkeypatch):
    calls = []

    def fake_request(path, *, method='GET', token=None, payload=None):
        calls.append((path, method, token))
        assert token == 'ephemeral-token'
        if path == '/v1/pki/issuers':
            return 200, {'data': {'keys': [ISSUER_ID],
                                  'key_info': {ISSUER_ID: {'issuer_name': 'root-ca'}}}}
        if path == f'/v1/pki/issuer/{ISSUER_ID}/json':
            return 200, {'data': {
                'certificate': certificate,
                'ca_chain': [certificate],
                'private_key': 'PRIVATE-KEY-NEVER-COPY',
                'private_key_type': 'exported',
                'key_id': 'test-only-key-id',
            }}
        pytest.fail('Only public PKI issuer endpoints may be queried')

    monkeypatch.setattr(client, '_request', fake_request)
    result = collect_pki_public_issuers(client, mount='pki')
    assert result.complete and len(result.issuers) == 1
    issuer = result.issuers[0]
    assert issuer.issuer_id == ISSUER_ID
    assert issuer.issuer_name == 'root-ca'
    assert len(issuer.certificate.fingerprint_sha256) == 64
    assert issuer.certificate.serial_hex == '65'
    assert issuer.certificate.is_ca is True
    assert issuer.certificate.self_issued is True
    assert issuer.certificate.dns_names == ('ca.internal.example',)
    assert issuer.trust_status == 'not_evaluated'
    assert issuer.revocation_status == 'not_evaluated'
    assert issuer.chain_fingerprints == (issuer.certificate.fingerprint_sha256,)
    assert calls == [
        ('/v1/pki/issuers', 'LIST', 'ephemeral-token'),
        (f'/v1/pki/issuer/{ISSUER_ID}/json', 'GET', 'ephemeral-token'),
    ]
    safe = repr(asdict(result))
    for disallowed in ('PRIVATE-KEY-NEVER-COPY', 'ephemeral-token', 'not-persisted', 'test-only-key-id'):
        assert disallowed not in safe
    assert certificate not in safe


@pytest.mark.parametrize('mount', ['', '../pki', 'pki//team', 'pki%2fhidden', 'pki?foo=bar'])
def test_refuses_unapproved_mount_path_without_login(mount, client, monkeypatch):
    monkeypatch.setattr(client, 'login', lambda: pytest.fail('Login should not be attempted'))
    with pytest.raises(VaultProviderError, match='mount'):
        collect_pki_public_issuers(client, mount=mount)


def test_unsupported_issuer_listing_is_not_healthy_empty(client, monkeypatch):
    monkeypatch.setattr(client, '_request', lambda *a, **k: (404, {}))
    with pytest.raises(VaultProviderError, match='unavailable'):
        collect_pki_public_issuers(client, mount='pki')


def test_issuer_count_bound_blocks_detail_reads(client, monkeypatch):
    calls = []

    def fake_request(path, **kwargs):
        calls.append(path)
        return 200, {'data': {'keys': [ISSUER_ID] * (MAX_ISSUERS + 1)}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='bound'):
        collect_pki_public_issuers(client, mount='pki')
    assert calls == ['/v1/pki/issuers']


def test_invalid_issuer_id_cannot_be_injected_into_api_path(client, monkeypatch):
    calls = []

    def fake_request(path, **kwargs):
        calls.append(path)
        return 200, {'data': {'keys': ['../../keys/export']}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='identity'):
        collect_pki_public_issuers(client, mount='pki')
    assert calls == ['/v1/pki/issuers']


def test_private_key_content_cannot_masquerade_as_public_certificate(client, monkeypatch):
    def fake_request(path, **kwargs):
        if path.endswith('/issuers'):
            return 200, {'data': {'keys': [ISSUER_ID]}}
        return 200, {'data': {'certificate': '-----BEGIN PRIVATE KEY-----SECRET', 'ca_chain': []}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='public certificate'):
        collect_pki_public_issuers(client, mount='pki')


def test_issuer_chain_must_remain_bounded(client, certificate, monkeypatch):
    def fake_request(path, **kwargs):
        if path.endswith('/issuers'):
            return 200, {'data': {'keys': [ISSUER_ID]}}
        return 200, {'data': {'certificate': certificate, 'ca_chain': [certificate] * 9}}

    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(VaultProviderError, match='chain'):
        collect_pki_public_issuers(client, mount='pki')
