"""Bounded, read-only Vault KV v2 metadata collector.

This is an in-memory source contract, not a committed inventory or a job adapter.
Only the Vault `metadata` endpoints are permitted. Never request `data` values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import quote

from app.integrations.secrets_management.secrets_pki.providers.vault.client import (
    VaultClient,
    VaultProviderError,
)

MAX_SECRETS = 200
MAX_VERSIONS_PER_SECRET = 100
MAX_DEPTH = 8
MAX_LIST_ENTRIES = 200


@dataclass(frozen=True, slots=True)
class KV2VersionEvidence:
    version: int
    created_time: str | None
    deletion_time: str | None
    destroyed: bool


@dataclass(frozen=True, slots=True)
class KV2SecretEvidence:
    # Paths are operationally sensitive metadata: never place objects in logs,
    # Celery payloads, URLs, unrestricted exports, or job result summaries.
    mount: str
    path: str = field(repr=False)
    current_version: int
    oldest_version: int
    max_versions: int
    cas_required: bool
    versions: tuple[KV2VersionEvidence, ...]


@dataclass(frozen=True, slots=True)
class KV2CollectionEvidence:
    """Safe evidence in process memory; no persistence is implied."""

    mount: str
    observed_at: datetime
    records: tuple[KV2SecretEvidence, ...] = field(repr=False)
    complete: bool = True


def _segments(value: str, *, required: bool) -> tuple[str, ...]:
    raw = str(value or '').strip('/')
    if not raw:
        if required:
            raise VaultProviderError('A KV v2 mount is required.')
        return ()
    if len(raw) > 1024:
        raise VaultProviderError('KV v2 path exceeds the supported bound.')
    parts = tuple(raw.split('/'))
    if any(
        not part
        or part in {'.', '..'}
        or any(char in part for char in '%?#')
        or '\\' in part
        or any(ord(char) < 32 or ord(char) == 127 for char in part)
        for part in parts
    ):
        raise VaultProviderError('KV v2 path contains an unsupported segment.')
    return parts


def _api_path(mount_parts: tuple[str, ...], secret_parts: tuple[str, ...]) -> str:
    # Percent-encode every path segment; never form a URI from unchecked input.
    segments = (*mount_parts, 'metadata', *secret_parts)
    return '/v1/' + '/'.join(quote(part, safe='-_.~') for part in segments)


def _version_number(value: object) -> int:
    if isinstance(value, bool):
        raise VaultProviderError('Invalid KV v2 version evidence.')
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal() and 1 <= len(value) <= 10:
        number = int(value)
    else:
        raise VaultProviderError('Invalid KV v2 version evidence.')
    # PostgreSQL integer columns must not overflow or truncate source facts.
    if not 0 <= number <= 2_147_483_647:
        raise VaultProviderError('Invalid KV v2 version evidence.')
    return number


def _safe_timestamp(value: object) -> str | None:
    """Normalize provider timestamps; never persist arbitrary provider strings."""
    if value is None or value == '':
        return None
    if not isinstance(value, str) or len(value) > 80:
        raise VaultProviderError('Malformed KV v2 metadata timestamp.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise VaultProviderError('Malformed KV v2 metadata timestamp.') from exc
    if parsed.tzinfo is None:
        raise VaultProviderError('KV v2 metadata timestamp lacks timezone.')
    return parsed.astimezone(UTC).isoformat()


def _safe_metadata(
    *,
    mount: str,
    path: str,
    body: dict,
) -> KV2SecretEvidence:
    data = body.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('versions'), dict):
        raise VaultProviderError('KV v2 metadata was absent or malformed.')
    versions = data['versions']
    if not isinstance(data.get('cas_required'), bool):
        raise VaultProviderError('KV v2 CAS posture is unavailable or malformed.')
    if len(versions) > MAX_VERSIONS_PER_SECRET:
        raise VaultProviderError('KV v2 version evidence exceeds the bounded scan.')
    normalized: list[KV2VersionEvidence] = []
    for raw_version, row in versions.items():
        if not isinstance(row, dict) or not isinstance(row.get('destroyed'), bool):
            raise VaultProviderError('KV v2 version evidence is malformed.')
        version = _version_number(raw_version)
        if version < 1:
            raise VaultProviderError('KV v2 version evidence is malformed.')
        normalized.append(
            KV2VersionEvidence(
                version=version,
                created_time=_safe_timestamp(row.get('created_time')),
                deletion_time=_safe_timestamp(row.get('deletion_time')),
                destroyed=row.get('destroyed') is True,
            )
        )
    normalized.sort(key=lambda item: item.version)
    if len({item.version for item in normalized}) != len(normalized):
        raise VaultProviderError('KV v2 metadata contains duplicate versions.')
    return KV2SecretEvidence(
        mount=mount,
        path=path,
        current_version=_version_number(data.get('current_version', 0)),
        oldest_version=_version_number(data.get('oldest_version', 0)),
        max_versions=_version_number(data.get('max_versions', 0)),
        cas_required=data.get('cas_required') is True,
        versions=tuple(normalized),
    )


def parse_approved_kv2_mounts(raw: str) -> tuple[str, ...]:
    """Parse an administrator's explicit, bounded mount allowlist."""
    if len(raw) > 1500:
        raise VaultProviderError('KV v2 mount configuration is too long.')
    values = [entry.strip().strip('/') for entry in raw.split(',') if entry.strip()]
    if len(values) > 8:
        raise VaultProviderError('A Vault instance supports at most eight approved KV v2 mounts.')
    mounts: list[str] = []
    for value in values:
        segments = _segments(value, required=True)
        normalized = '/'.join(segments)
        if len(normalized) > 160:
            raise VaultProviderError('A KV v2 mount name is too long.')
        if normalized in mounts:
            raise VaultProviderError('KV v2 mount configuration contains duplicates.')
        mounts.append(normalized)
    return tuple(mounts)


def collect_kv2_metadata(
    client: VaultClient,
    *,
    mount: str,
    max_secrets: int = MAX_SECRETS,
) -> KV2CollectionEvidence:
    """Collect metadata for one explicitly selected KV v2 mount.

    A 403, 404, malformed response, failed discovery or scan limit raises a
    sanitized error. The caller must **not** commit a partial/empty snapshot
    when an error is raised. Version 1 engines are not supported here.
    """
    mount_parts = _segments(mount, required=True)
    if not 1 <= max_secrets <= MAX_SECRETS:
        raise VaultProviderError('Invalid KV v2 inventory scan bound.')
    token = client.login()
    stack: list[tuple[tuple[str, ...], int]] = [((), 0)]
    records: list[KV2SecretEvidence] = []
    seen: set[tuple[str, ...]] = set()
    directories: set[tuple[str, ...]] = set()
    while stack:
        prefix, depth = stack.pop()
        if prefix in directories:
            raise VaultProviderError('KV v2 directory discovery contains duplicates.')
        directories.add(prefix)
        if len(directories) > MAX_SECRETS:
            raise VaultProviderError('KV v2 directory discovery exceeds the bounded scan.')
        status, response = client._request(
            _api_path(mount_parts, prefix),
            method='LIST',
            token=token,
        )
        if status != 200 or not isinstance(response.get('data'), dict):
            raise VaultProviderError('Vault KV v2 metadata listing is unavailable or unauthorized.')
        keys = response['data'].get('keys')
        if not isinstance(keys, list) or len(keys) > MAX_LIST_ENTRIES:
            raise VaultProviderError('Vault KV v2 metadata listing is malformed or too large.')
        for raw_key in keys:
            if not isinstance(raw_key, str) or not raw_key:
                raise VaultProviderError('Vault KV v2 listing contained an invalid key.')
            folder = raw_key.endswith('/')
            parts = _segments(raw_key, required=True)
            if len(parts) != 1:
                raise VaultProviderError('Vault KV v2 listing contained an unsafe key segment.')
            target = (*prefix, parts[0])
            if depth + 1 > MAX_DEPTH:
                raise VaultProviderError('KV v2 inventory exceeds maximum directory depth.')
            if folder:
                if len(stack) + len(directories) >= MAX_SECRETS:
                    raise VaultProviderError('KV v2 directory discovery exceeds the bounded scan.')
                stack.append((target, depth + 1))
                continue
            if target in seen:
                raise VaultProviderError('KV v2 listing contained duplicate secret identities.')
            seen.add(target)
            if len(seen) > max_secrets:
                raise VaultProviderError('KV v2 metadata exceeds maximum secret count.')
            result_status, body = client._request(
                _api_path(mount_parts, target),
                token=token,
            )
            if result_status != 200:
                raise VaultProviderError('Vault KV v2 metadata detail is unavailable or unauthorized.')
            records.append(
                _safe_metadata(
                    mount='/'.join(mount_parts),
                    path='/'.join(target),
                    body=body,
                )
            )
    return KV2CollectionEvidence(
        mount='/'.join(mount_parts),
        observed_at=datetime.now(UTC),
        records=tuple(sorted(records, key=lambda item: item.path)),
    )
