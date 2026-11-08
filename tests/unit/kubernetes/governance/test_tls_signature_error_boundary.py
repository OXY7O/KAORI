"""Narrow RSA signature errors without weakening certificate pair validity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.governance.tls_certificates import certificate


class _InvalidSignature(Exception):
    pass


class _RSAKey:
    def sign(self, *_args: object) -> bytes:
        return b'signature'


class _ForeignPublicKey:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def verify(self, *_args: object) -> None:
        raise self.error


class _ForeignCertificate:
    def __init__(self, error: Exception) -> None:
        self.public_key_object = _ForeignPublicKey(error)

    def public_key(self) -> _ForeignPublicKey:
        return self.public_key_object


class _NotRSA:
    pass


def _mock_crypto(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    certificate_object = _ForeignCertificate(error)
    crypto = SimpleNamespace(
        x509=SimpleNamespace(load_pem_x509_certificate=lambda _pem: certificate_object),
        serialization=SimpleNamespace(load_pem_private_key=lambda _key, password=None: _RSAKey()),
        rsa=SimpleNamespace(RSAPrivateKey=_RSAKey, RSAPublicKey=_NotRSA),
        ec=SimpleNamespace(EllipticCurvePrivateKey=_NotRSA, EllipticCurvePublicKey=_NotRSA),
        ed25519=SimpleNamespace(Ed25519PrivateKey=_NotRSA),
        ed448=SimpleNamespace(Ed448PrivateKey=_NotRSA),
        hashes=SimpleNamespace(SHA256=lambda: object()),
        padding=SimpleNamespace(PKCS1v15=lambda: object()),
        invalid_signature=_InvalidSignature,
    )
    monkeypatch.setattr(certificate, '_load_crypto', lambda: crypto)


@pytest.mark.parametrize('error', [_InvalidSignature(), TypeError('wrong key shape'), ValueError('invalid key')])
def test_expected_rsa_signature_mismatch_is_rejected(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    _mock_crypto(monkeypatch, error)
    assert not certificate._public_key_matches_certificate(b'certificate', b'private-key')


def test_unexpected_crypto_defect_propagates_from_private_matcher(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_crypto(monkeypatch, LookupError('unexpected crypto backend defect'))

    with pytest.raises(LookupError, match='unexpected crypto backend defect'):
        certificate._public_key_matches_certificate(b'certificate', b'private-key')


def test_public_certificate_pair_validation_remains_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_crypto(monkeypatch, LookupError('unexpected crypto backend defect'))
    now = datetime.now(UTC)
    parsed = certificate.ParsedCertificate(
        common_name='api.example.invalid',
        issuer='Test CA',
        serial_number='1',
        fingerprint_sha256='0000',
        dns_names=['api.example.invalid'],
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=20),
        days_remaining=20,
        status='healthy',
        risk_level='healthy',
    )
    monkeypatch.setattr(certificate, 'parse_certificate', lambda *_args, **_kwargs: parsed)

    result = certificate.validate_certificate_pair(b'certificate', b'private-key')
    assert result.is_valid is False
    assert any('match validation failed' in error for error in result.errors)
