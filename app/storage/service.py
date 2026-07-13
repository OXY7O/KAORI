from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flask import current_app

from app.storage.base import ArtifactStorageBackend
from app.storage.local import LocalArtifactStorage
from app.storage.s3 import S3ArtifactStorage


@dataclass(frozen=True)
class StorageProfile:
    name: str
    backend: str
    local_root: Path
    download_cache: Path
    s3_bucket: str
    s3_region: str
    s3_endpoint_url: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None
    s3_prefix: str
    s3_force_path_style: bool


def parse_bool_config(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def resolve_app_path(value: str | Path | None, default: Path) -> Path:
    path = Path(value) if value else default
    if not path.is_absolute():
        path = Path(current_app.root_path).parent / path
    return path.resolve()


def build_storage_profile(profile_name: str) -> StorageProfile:
    prefix = profile_name.strip().upper()
    if not prefix:
        raise ValueError('Storage profile name is required.')

    backend = str(current_app.config.get(f'{prefix}_STORAGE_BACKEND', 'local') or 'local').strip().lower()
    if backend not in {'local', 's3'}:
        raise RuntimeError(f'Unsupported {profile_name} storage backend: {backend}.')

    return StorageProfile(
        name=profile_name.lower(),
        backend=backend,
        local_root=resolve_app_path(
            current_app.config.get(f'{prefix}_LOCAL_STORAGE_DIR'),
            Path(current_app.instance_path),
        ),
        download_cache=resolve_app_path(
            current_app.config.get(f'{prefix}_DOWNLOAD_CACHE_DIR'),
            Path(current_app.instance_path) / f'{profile_name.lower()}-download-cache',
        ),
        s3_bucket=str(current_app.config.get(f'{prefix}_S3_BUCKET', '') or '').strip(),
        s3_region=str(current_app.config.get(f'{prefix}_S3_REGION', 'us-east-1') or 'us-east-1').strip(),
        s3_endpoint_url=current_app.config.get(f'{prefix}_S3_ENDPOINT_URL'),
        s3_access_key_id=current_app.config.get(f'{prefix}_S3_ACCESS_KEY_ID'),
        s3_secret_access_key=current_app.config.get(f'{prefix}_S3_SECRET_ACCESS_KEY'),
        s3_prefix=str(current_app.config.get(f'{prefix}_S3_PREFIX', '') or '').strip().strip('/'),
        s3_force_path_style=parse_bool_config(current_app.config.get(f'{prefix}_S3_FORCE_PATH_STYLE', False)),
    )


def build_artifact_storage(profile_name: str) -> ArtifactStorageBackend:
    profile = build_storage_profile(profile_name)
    return build_artifact_storage_for_backend(profile_name, profile.backend)


def build_artifact_storage_for_backend(
    profile_name: str,
    backend_name: str,
    *,
    locator: dict[str, object] | None = None,
) -> ArtifactStorageBackend:
    profile = build_storage_profile(profile_name)
    normalized_backend = backend_name.strip().lower()
    locator = dict(locator or {})

    if normalized_backend == 'local':
        local_root = resolve_app_path(
            locator.get('local_root') or profile.local_root,
            profile.local_root,
        )
        return LocalArtifactStorage(root_dir=local_root)

    if normalized_backend != 's3':
        raise RuntimeError(f'Unsupported {profile_name} storage backend: {backend_name}.')

    bucket = locator['s3_bucket'] if 's3_bucket' in locator else profile.s3_bucket
    region = locator['s3_region'] if 's3_region' in locator else profile.s3_region
    endpoint_url = (
        locator['s3_endpoint_url']
        if 's3_endpoint_url' in locator
        else profile.s3_endpoint_url
    )
    s3_prefix = locator['s3_prefix'] if 's3_prefix' in locator else profile.s3_prefix
    force_path_style = (
        locator['s3_force_path_style']
        if 's3_force_path_style' in locator
        else profile.s3_force_path_style
    )

    return S3ArtifactStorage(
        bucket=str(bucket or ''),
        cache_dir=profile.download_cache,
        region=str(region or 'us-east-1'),
        endpoint_url=str(endpoint_url) if endpoint_url else None,
        access_key_id=profile.s3_access_key_id,
        secret_access_key=profile.s3_secret_access_key,
        prefix=str(s3_prefix or ''),
        force_path_style=parse_bool_config(force_path_style),
    )


def build_storage_locator(profile_name: str) -> dict[str, object]:
    """Return a non-secret storage snapshot for durable archive registry rows."""
    profile = build_storage_profile(profile_name)
    return {
        'profile_name': profile.name,
        'backend': profile.backend,
        'local_root': str(profile.local_root),
        's3_bucket': profile.s3_bucket,
        's3_region': profile.s3_region,
        's3_endpoint_url': profile.s3_endpoint_url,
        's3_prefix': profile.s3_prefix,
        's3_force_path_style': profile.s3_force_path_style,
    }


def parse_storage_uri(uri: str) -> tuple[str, str]:
    if not uri or ':' not in uri:
        raise ValueError('Artifact storage URI must use the <backend>:<object-key> format.')
    backend, object_key = uri.split(':', 1)
    backend = backend.strip().lower()
    object_key = object_key.strip().lstrip('/')
    if backend not in {'local', 's3'} or not object_key:
        raise ValueError('Artifact storage URI is invalid.')
    return backend, object_key
