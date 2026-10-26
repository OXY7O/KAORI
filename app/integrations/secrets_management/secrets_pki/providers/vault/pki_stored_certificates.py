"""Bounded, read-only Vault *stored* PKI certificate observations.

The authenticated LIST /certs endpoint excludes no_store=true certificates,
imported issuers and other sources. This is never an all-issued-certs view.
Public certificate PEM is decoded only in worker memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.integrations.secrets_management.secrets_pki.providers.vault.client import (
    VaultClient,
    VaultProviderError,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    PublicCertificateEvidence,
    _parse_certificate,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.transport import validate_auth_mount

MAX_STORED_CERTIFICATES = 64
_SERIAL_RE = re.compile(r'[0-9a-f]{2}(?::[0-9a-f]{2}){0,49}\Z')


@dataclass(frozen=True, slots=True)
class StoredCertificateEvidence:
    # Serials and X.509 names can reveal infrastructure metadata; never log.
    serial_hex: str = field(repr=False)
    certificate: PublicCertificateEvidence = field(repr=False)


@dataclass(frozen=True, slots=True)
class StoredCertificateCollection:
    mount: str = field(repr=False)
    observed_at: datetime
    certificates: tuple[StoredCertificateEvidence, ...] = field(repr=False)
    complete: bool = True
    coverage: str = 'vault_stored_only'


def _serial(value: object) -> str:
    if not isinstance(value, str) or not _SERIAL_RE.fullmatch(value):
        raise VaultProviderError('Vault stored certificate serial is malformed.')
    return value


def collect_pki_stored_certificates(
    client: VaultClient,
    *,
    mount: str,
) -> StoredCertificateCollection:
    """Never paginate or silently truncate an over-bound full listing."""
    try:
        mount_name = validate_auth_mount(mount)
    except ValueError as exc:
        raise VaultProviderError('PKI stored certificate mount is not a safe segment.') from exc
    token = client.login()
    status, payload = client._request(f'/v1/{mount_name}/certs', method='LIST', token=token)
    body = payload.get('data') if isinstance(payload, dict) else None
    if status != 200 or not isinstance(body, dict) or not isinstance(body.get('keys'), list):
        raise VaultProviderError('Vault stored certificate listing is unavailable.')
    keys = body['keys']
    if len(keys) > MAX_STORED_CERTIFICATES:
        raise VaultProviderError('Vault stored certificate count exceeds bounded read profile.')
    serials = [_serial(item) for item in keys]
    canonical = [format(int(serial.replace(':', ''), 16), 'x') for serial in serials]
    if len(set(canonical)) != len(canonical):
        raise VaultProviderError('Vault stored certificate listing has duplicate serials.')
    observations: list[StoredCertificateEvidence] = []
    for serial, normalized in zip(serials, canonical, strict=True):
        response_status, result = client._request(
            f'/v1/{mount_name}/cert/{serial}',
            token=token,
        )
        cert_data = result.get('data') if isinstance(result, dict) else None
        if response_status != 200 or not isinstance(cert_data, dict):
            raise VaultProviderError('Vault stored certificate read is unavailable.')
        _, parsed = _parse_certificate(cert_data.get('certificate'))
        if int(parsed.serial_hex, 16) != int(serial.replace(':', ''), 16):
            raise VaultProviderError('Vault stored certificate serial differs from public certificate.')
        observations.append(StoredCertificateEvidence(serial_hex=normalized, certificate=parsed))
    return StoredCertificateCollection(
        mount=mount_name,
        observed_at=datetime.now(UTC),
        certificates=tuple(observations),
    )
