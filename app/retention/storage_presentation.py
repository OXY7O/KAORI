from __future__ import annotations

import os
import socket
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlparse

from app.models.archive import ArchiveArtifact
from app.storage.service import StorageProfile

_STATUS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def build_storage_context(
    profile: StorageProfile,
    last_verified: ArchiveArtifact | None,
) -> dict[str, Any]:
    provider = _storage_provider_label(profile.backend, profile.s3_endpoint_url)
    verified_artifact = last_verified if artifact_matches_storage_profile(last_verified, profile) else None
    status = 'configured'
    status_label = 'Configured'
    status_tone = 'blue'
    detail = 'Archive target is configured and will be verified during every lifecycle run.'

    if profile.backend == 'local':
        root = Path(profile.local_root)
        try:
            root.mkdir(parents=True, exist_ok=True)
            writable = root.is_dir() and os.access(root, os.W_OK | os.X_OK)
        except OSError:
            writable = False
        if writable:
            status = 'ready'
            status_label = 'Ready'
            status_tone = 'emerald'
            detail = 'The local archive directory is available to KAORI.'
        else:
            status = 'unavailable'
            status_label = 'Unavailable'
            status_tone = 'rose'
            detail = 'The local archive directory is not available to KAORI.'
    elif not profile.s3_bucket:
        status = 'incomplete'
        status_label = 'Incomplete'
        status_tone = 'amber'
        detail = 'An S3-compatible bucket is required before archive jobs can run.'
    elif verified_artifact is not None and verified_artifact.storage_backend == 's3':
        status = 'verified'
        status_label = 'Verified'
        status_tone = 'emerald'
        detail = 'A previous archive was uploaded and checksum-verified on this S3-compatible backend.'
    elif profile.s3_endpoint_url is not None:
        endpoint_url = profile.s3_endpoint_url
        endpoint_probe = _cached_status(
            f'archive-storage:{endpoint_url}',
            20.0,
            lambda: _probe_storage_endpoint(endpoint_url),
        )
        if endpoint_probe['reachable']:
            status = 'reachable'
            status_label = 'Reachable'
            status_tone = 'emerald'
            detail = 'The configured S3-compatible endpoint is reachable from the KAORI web container.'
        else:
            status = 'unreachable'
            status_label = 'Unreachable'
            status_tone = 'rose'
            detail = endpoint_probe['detail']

    return {
        'backend': profile.backend,
        'provider_label': provider,
        'status': status,
        'status_label': status_label,
        'status_tone': status_tone,
        'detail': detail,
        'location': _storage_location(profile),
        'endpoint_label': _storage_endpoint_label(profile),
        'bucket': profile.s3_bucket if profile.backend == 's3' else None,
        'last_verified_at': verified_artifact.verified_at if verified_artifact else None,
    }


def build_storage_contract_context(profile: StorageProfile) -> dict[str, Any]:
    """Return configuration-only archive storage metadata without probing the backend."""
    return {
        'backend': profile.backend,
        'provider_label': _storage_provider_label(profile.backend, profile.s3_endpoint_url),
        'location': _storage_location(profile),
        'endpoint_label': _storage_endpoint_label(profile),
        'bucket': profile.s3_bucket if profile.backend == 's3' else None,
    }


def artifact_matches_storage_profile(
    artifact: ArchiveArtifact | None,
    profile: StorageProfile,
) -> bool:
    if artifact is None or artifact.storage_backend != profile.backend:
        return False
    metadata = artifact.metadata_json or {}
    locator = metadata.get('storage_locator') if isinstance(metadata, dict) else None
    if not isinstance(locator, dict):
        return False
    if profile.backend == 'local':
        archived_root = str(locator.get('local_root') or '').strip()
        return bool(archived_root) and Path(archived_root).resolve() == profile.local_root.resolve()
    return (
        str(locator.get('s3_bucket') or '').strip() == profile.s3_bucket
        and str(locator.get('s3_endpoint_url') or '').strip().rstrip('/')
        == str(profile.s3_endpoint_url or '').strip().rstrip('/')
        and str(locator.get('s3_prefix') or '').strip().strip('/') == profile.s3_prefix
    )


def archive_storage_label(backend: str | None, locator: Any) -> str:
    normalized_backend = str(backend or '').strip().lower()
    if normalized_backend == 'local':
        return 'Local filesystem'
    if normalized_backend != 's3':
        return normalized_backend.upper() if normalized_backend else '-'
    endpoint = None
    if isinstance(locator, dict):
        endpoint = locator.get('s3_endpoint_url')
    return _storage_provider_label('s3', str(endpoint) if endpoint else None)


def _probe_storage_endpoint(endpoint_url: str) -> dict[str, Any]:
    parsed = urlparse(endpoint_url)
    host = parsed.hostname
    if not host:
        return {
            'reachable': False,
            'detail': 'Archive storage configuration is invalid.',
        }
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return {
                'reachable': True,
                'detail': f'{host}:{port} accepted a TCP connection.',
            }
    except OSError:
        return {
            'reachable': False,
            'detail': 'Archive storage is currently unavailable.',
        }


def _cached_status(
    key: str,
    ttl_seconds: float,
    loader,
) -> dict[str, Any]:
    now = monotonic()
    cached = _STATUS_CACHE.get(key)
    if cached and now - cached[0] < ttl_seconds:
        return dict(cached[1])
    value = loader()
    _STATUS_CACHE[key] = (now, dict(value))
    return value


def _storage_provider_label(backend: str, endpoint_url: str | None) -> str:
    if backend == 'local':
        return 'Local filesystem'
    endpoint = str(endpoint_url or '').strip().lower()
    hostname = (urlparse(endpoint).hostname or '').lower() if endpoint else ''
    if 'minio' in endpoint or hostname.startswith('minio') or ':9000' in endpoint or ':9001' in endpoint:
        return 'MinIO'
    if not endpoint or 'amazonaws.com' in endpoint:
        return 'Amazon S3'
    return 'S3-compatible'


def _storage_endpoint_label(profile: StorageProfile) -> str | None:
    if profile.backend == 'local':
        return None
    endpoint = str(profile.s3_endpoint_url or '').strip()
    if not endpoint:
        return 'AWS endpoint'
    parsed = urlparse(endpoint)
    return parsed.netloc or endpoint


def _storage_location(profile: StorageProfile) -> str:
    if profile.backend == 'local':
        return str(profile.local_root)
    prefix = f'/{profile.s3_prefix}' if profile.s3_prefix else ''
    return f's3://{profile.s3_bucket}{prefix}'
