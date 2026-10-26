"""Vault PKI issuer discovery with certificate-only, bounded evidence.

A qualified source contract, not a trust verdict or a committed PKI inventory.
Only LIST issuers and GET issuer/<UUID>/json are allowed. Never call the
privileged issuer read endpoint, export endpoints or issuance/revocation APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes

from app.integrations.secrets_management.secrets_pki.providers.vault.client import (
    VaultClient,
    VaultProviderError,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.transport import (
    validate_auth_mount,
)

MAX_ISSUERS = 24
MAX_CHAIN_CERTIFICATES = 8
MAX_CERTIFICATE_PEM_BYTES = 32768
MAX_DNS_NAMES = 32
MAX_PKI_MOUNTS = 4


def parse_approved_pki_mounts(value: str) -> tuple[str, ...]:
    """Only explicit bounded PKI mounts. Invalid scopes never broaden discovery."""
    raw = str(value or '')
    if not raw.strip():
        return ()
    names = raw.split(',')
    if len(names) > MAX_PKI_MOUNTS:
        raise ValueError('Vault PKI collection allows at most four approved mounts.')
    normalized: list[str] = []
    for item in names:
        candidate = item.strip()
        if not candidate or candidate.startswith('/') or candidate.endswith('/'):
            raise ValueError('Vault PKI mounts must be explicit single segments.')
        try:
            mount = validate_auth_mount(candidate)
        except ValueError as exc:
            raise ValueError('Vault PKI mount must be a safe single path segment.') from exc
        if mount in normalized:
            raise ValueError('Duplicate Vault PKI mounts are not allowed.')
        normalized.append(mount)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class PublicCertificateEvidence:
    fingerprint_sha256: str
    serial_hex: str
    subject: str = field(repr=False)
    issuer: str = field(repr=False)
    valid_from: datetime
    valid_until: datetime
    is_ca: bool | None
    self_issued: bool
    dns_names: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class PKIIssuerEvidence:
    issuer_id: str
    issuer_name: str | None = field(repr=False)
    certificate: PublicCertificateEvidence
    chain_fingerprints: tuple[str, ...]
    revocation_status: str = 'not_evaluated'
    trust_status: str = 'not_evaluated'


@dataclass(frozen=True, slots=True)
class PKIIssuerCollection:
    mount: str = field(repr=False)
    observed_at: datetime
    issuers: tuple[PKIIssuerEvidence, ...]
    complete: bool = True


def _normalized_issuer_id(raw: object) -> str:
    if not isinstance(raw, str) or len(raw) > 64:
        raise VaultProviderError('Malformed Vault PKI issuer identity.')
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError) as exc:
        raise VaultProviderError('Malformed Vault PKI issuer identity.') from exc


def _issuer_name(raw: object) -> str | None:
    if raw is None or raw == '':
        return None
    if not isinstance(raw, str) or len(raw) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise VaultProviderError('Malformed Vault PKI issuer label.')
    return raw


def _parse_certificate(raw: object) -> tuple[x509.Certificate, PublicCertificateEvidence]:
    if (
        not isinstance(raw, str)
        or not raw.startswith('-----BEGIN CERTIFICATE-----')
        or len(raw) > MAX_CERTIFICATE_PEM_BYTES
    ):
        raise VaultProviderError('Vault PKI public certificate is missing or out of bounds.')
    try:
        cert = x509.load_pem_x509_certificate(raw.encode('ascii'))
    except (ValueError, UnicodeEncodeError, UnsupportedAlgorithm) as exc:
        raise VaultProviderError('Vault PKI public certificate could not be decoded.') from exc
    before = getattr(cert, 'not_valid_before_utc', None)
    after = getattr(cert, 'not_valid_after_utc', None)
    if before is None:
        before = cert.not_valid_before.replace(tzinfo=UTC)
    if after is None:
        after = cert.not_valid_after.replace(tzinfo=UTC)
    try:
        constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        is_ca: bool | None = constraints.ca
    except x509.ExtensionNotFound:
        is_ca = None
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns = san.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        dns = []
    if len(dns) > MAX_DNS_NAMES or any(len(value) > 255 for value in dns):
        raise VaultProviderError('Vault PKI certificate DNS evidence exceeded the bounded profile.')
    subject = cert.subject.rfc4514_string()
    issuer = cert.issuer.rfc4514_string()
    if len(subject) > 1000 or len(issuer) > 1000 or any(ord(c) < 32 for c in subject + issuer):
        raise VaultProviderError('Vault PKI certificate identity exceeds the bounded profile.')
    return cert, PublicCertificateEvidence(
        fingerprint_sha256=cert.fingerprint(hashes.SHA256()).hex(),
        serial_hex=format(cert.serial_number, 'x'),
        subject=subject,
        issuer=issuer,
        valid_from=before,
        valid_until=after,
        is_ca=is_ca,
        # Names alone do not prove self-signature or trusted root status.
        self_issued=cert.subject == cert.issuer,
        dns_names=tuple(dns),
    )


def collect_pki_public_issuers(client: VaultClient, *, mount: str) -> PKIIssuerCollection:
    """Observe one explicit PKI engine mount, without reading privileged key APIs."""
    try:
        mount_name = validate_auth_mount(mount)
    except ValueError as exc:
        raise VaultProviderError('Vault PKI mount must be a safe, explicitly approved segment.') from exc
    token = client.login()
    status, body = client._request(f'/v1/{mount_name}/issuers', method='LIST', token=token)
    data = body.get('data')
    if status != 200 or not isinstance(data, dict):
        raise VaultProviderError('Vault PKI issuer discovery is unavailable or unsupported.')
    keys = data.get('keys')
    key_info = data.get('key_info') or {}
    if not isinstance(keys, list) or len(keys) > MAX_ISSUERS or not isinstance(key_info, dict):
        raise VaultProviderError('Vault PKI issuer listing is malformed or above the scan bound.')
    issuer_ids = [_normalized_issuer_id(key) for key in keys]
    if len(issuer_ids) != len(set(issuer_ids)):
        raise VaultProviderError('Vault PKI issuer listing contains duplicate identifiers.')
    records: list[PKIIssuerEvidence] = []
    for issuer_id in issuer_ids:
        info = key_info.get(issuer_id) or {}
        if not isinstance(info, dict):
            raise VaultProviderError('Vault PKI issuer metadata is malformed.')
        name = _issuer_name(info.get('issuer_name'))
        response_status, payload = client._request(
            f'/v1/{mount_name}/issuer/{issuer_id}/json',
            token=token,
        )
        evidence = payload.get('data')
        if response_status != 200 or not isinstance(evidence, dict):
            raise VaultProviderError('Vault PKI public issuer certificate is unavailable.')
        _, certificate = _parse_certificate(evidence.get('certificate'))
        chain = evidence.get('ca_chain') or []
        if not isinstance(chain, list) or len(chain) > MAX_CHAIN_CERTIFICATES:
            raise VaultProviderError('Vault PKI issuer chain is malformed or too large.')
        chain_fingerprints = tuple(_parse_certificate(item)[1].fingerprint_sha256 for item in chain)
        records.append(
            PKIIssuerEvidence(
                issuer_id=issuer_id,
                issuer_name=name,
                certificate=certificate,
                chain_fingerprints=chain_fingerprints,
            )
        )
    return PKIIssuerCollection(
        mount=mount_name,
        observed_at=datetime.now(UTC),
        issuers=tuple(records),
    )
