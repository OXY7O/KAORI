from __future__ import annotations

import base64
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple

from app.governance.tls_certificates.constants import (
    TLS_STATUS_CRITICAL,
    TLS_STATUS_EXPIRED,
    TLS_STATUS_HEALTHY,
    TLS_STATUS_WARNING,
)


@dataclass(frozen=True)
class ParsedCertificate:
    common_name: str | None
    issuer: str | None
    serial_number: str
    fingerprint_sha256: str
    dns_names: list[str]
    not_before: datetime
    not_after: datetime
    days_remaining: int
    status: str
    risk_level: str


@dataclass(frozen=True)
class CertificatePairValidation:
    is_valid: bool
    parsed_certificate: ParsedCertificate | None
    errors: list[str]
    warnings: list[str]


class _CryptoModules(NamedTuple):
    x509: Any
    invalid_signature: Any
    hashes: Any
    serialization: Any
    ec: Any
    ed25519: Any
    ed448: Any
    padding: Any
    rsa: Any


def _load_crypto() -> _CryptoModules:
    """Import cryptography lazily so Flask can boot and migrations can run.

    The TLS Governance feature needs cryptography for X.509 parsing and
    certificate/key matching. Keeping the import lazy prevents the whole Flask
    application from failing to import before dependencies are installed.
    """
    try:
        from cryptography import x509
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, padding, rsa
    except ModuleNotFoundError as exc:
        if exc.name == 'cryptography':
            raise RuntimeError(
                "TLS Certificates requires the 'cryptography' package. Install it with: pip install cryptography"
            ) from exc
        raise
    return _CryptoModules(
        x509=x509,
        invalid_signature=InvalidSignature,
        hashes=hashes,
        serialization=serialization,
        ec=ec,
        ed25519=ed25519,
        ed448=ed448,
        padding=padding,
        rsa=rsa,
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def decode_secret_data(value: str | None) -> bytes:
    if not value:
        return b''
    return base64.b64decode(value)


def parse_certificate(cert_bytes: bytes) -> ParsedCertificate:
    crypto = _load_crypto()
    certificate = crypto.x509.load_pem_x509_certificate(cert_bytes)

    common_name = None
    common_name_attributes = certificate.subject.get_attributes_for_oid(crypto.x509.NameOID.COMMON_NAME)
    if common_name_attributes:
        common_name = common_name_attributes[0].value

    issuer = ', '.join(attribute.rfc4514_string() for attribute in certificate.issuer)

    dns_names: list[str] = []
    try:
        san = certificate.extensions.get_extension_for_class(crypto.x509.SubjectAlternativeName)
        dns_names = list(san.value.get_values_for_type(crypto.x509.DNSName))
    except crypto.x509.ExtensionNotFound:
        dns_names = []

    not_before_value = getattr(certificate, 'not_valid_before_utc', None) or certificate.not_valid_before
    not_after_value = getattr(certificate, 'not_valid_after_utc', None) or certificate.not_valid_after
    not_before = _ensure_aware(not_before_value)
    not_after = _ensure_aware(not_after_value)
    now = datetime.now(UTC)
    days_remaining = (not_after - now).days

    if days_remaining <= 0:
        status = TLS_STATUS_EXPIRED
        risk_level = 'critical'
    elif days_remaining <= 7:
        status = TLS_STATUS_CRITICAL
        risk_level = 'critical'
    elif days_remaining <= 30:
        status = TLS_STATUS_WARNING
        risk_level = 'warning'
    else:
        status = TLS_STATUS_HEALTHY
        risk_level = 'healthy'

    return ParsedCertificate(
        common_name=common_name,
        issuer=issuer or None,
        serial_number=format(certificate.serial_number, 'x'),
        fingerprint_sha256=certificate.fingerprint(crypto.hashes.SHA256()).hex(),
        dns_names=dns_names,
        not_before=not_before,
        not_after=not_after,
        days_remaining=days_remaining,
        status=status,
        risk_level=risk_level,
    )


def _public_key_matches_certificate(cert_bytes: bytes, key_bytes: bytes) -> bool:
    crypto = _load_crypto()
    certificate = crypto.x509.load_pem_x509_certificate(cert_bytes)
    private_key = crypto.serialization.load_pem_private_key(key_bytes, password=None)
    public_key = certificate.public_key()

    if isinstance(private_key, crypto.rsa.RSAPrivateKey) and isinstance(public_key, crypto.rsa.RSAPublicKey):
        return private_key.public_key().public_numbers() == public_key.public_numbers()

    if isinstance(private_key, crypto.ec.EllipticCurvePrivateKey) and isinstance(
        public_key, crypto.ec.EllipticCurvePublicKey
    ):
        return private_key.public_key().public_numbers() == public_key.public_numbers()

    if isinstance(private_key, (crypto.ed25519.Ed25519PrivateKey, crypto.ed448.Ed448PrivateKey)):
        message = b'kaori-tls-validation'
        signature = private_key.sign(message)
        try:
            public_key.verify(signature, message)  # type: ignore[attr-defined]
            return True
        except crypto.invalid_signature:
            return False

    try:
        message = b'kaori-tls-validation'
        if isinstance(private_key, crypto.rsa.RSAPrivateKey):
            signature = private_key.sign(message, crypto.padding.PKCS1v15(), crypto.hashes.SHA256())
            public_key.verify(signature, message, crypto.padding.PKCS1v15(), crypto.hashes.SHA256())  # type: ignore[attr-defined]
            return True
    except Exception:
        return False

    return False


def validate_certificate_pair(cert_bytes: bytes, key_bytes: bytes) -> CertificatePairValidation:
    errors: list[str] = []
    warnings: list[str] = []
    parsed: ParsedCertificate | None = None

    if not cert_bytes:
        errors.append('Certificate file is required.')
    if not key_bytes:
        errors.append('Private key file is required.')

    if errors:
        return CertificatePairValidation(False, None, errors, warnings)

    try:
        parsed = parse_certificate(cert_bytes)
    except Exception as exc:
        errors.append(f'Certificate cannot be parsed as a valid PEM X.509 certificate: {exc}')

    try:
        crypto = _load_crypto()
        crypto.serialization.load_pem_private_key(key_bytes, password=None)
    except Exception as exc:
        errors.append(f'Private key cannot be parsed as an unencrypted PEM key: {exc}')

    if not errors:
        try:
            if not _public_key_matches_certificate(cert_bytes, key_bytes):
                errors.append('Certificate and private key do not match.')
        except Exception as exc:
            errors.append(f'Certificate/key match validation failed: {exc}')

    if parsed and parsed.days_remaining <= 0:
        errors.append('Certificate is already expired.')

    if parsed and not parsed.dns_names and not parsed.common_name:
        warnings.append('Certificate does not expose SAN DNS names or a Common Name.')

    return CertificatePairValidation(not errors, parsed, errors, warnings)


def hostname_matches_pattern(hostname: str, pattern: str) -> bool:
    hostname = hostname.lower().strip()
    pattern = pattern.lower().strip()

    if not hostname or not pattern:
        return False

    if pattern == hostname:
        return True

    if pattern.startswith('*.'):
        suffix = pattern[1:]
        return hostname.endswith(suffix) and hostname.count('.') >= pattern.count('.')

    return False


def find_uncovered_hosts(hosts: Iterable[str], parsed_certificate: ParsedCertificate) -> list[str]:
    patterns = parsed_certificate.dns_names or (
        [parsed_certificate.common_name] if parsed_certificate.common_name else []
    )
    uncovered: list[str] = []

    for host in sorted({item for item in hosts if item}):
        if not any(hostname_matches_pattern(host, pattern) for pattern in patterns if pattern):
            uncovered.append(host)

    return uncovered
