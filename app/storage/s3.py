from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.storage.base import ArtifactStat, StoredArtifact


class S3ArtifactStorage:
    backend_name = 's3'

    def __init__(
        self,
        *,
        bucket: str,
        cache_dir: Path,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        prefix: str | None = None,
        force_path_style: bool = False,
        connect_timeout_seconds: int = 2,
        read_timeout_seconds: int = 3,
        max_attempts: int = 1,
    ) -> None:
        if not bucket:
            raise RuntimeError('An S3 bucket is required for S3-compatible artifact storage.')

        try:
            import boto3  # type: ignore[import-not-found]
            from botocore.config import Config as BotoCoreConfig  # type: ignore[import-not-found]
            from botocore.exceptions import ClientError  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError('boto3 is required for S3-compatible artifact storage.') from exc

        self.bucket = bucket
        self.cache_dir = cache_dir
        self.prefix = normalize_s3_prefix(prefix)

        client_kwargs: dict[str, Any] = {
            'region_name': region or 'us-east-1',
        }
        if endpoint := normalize_optional_string(endpoint_url):
            client_kwargs['endpoint_url'] = endpoint

        normalized_access_key = normalize_optional_string(access_key_id)
        normalized_secret_key = normalize_optional_string(secret_access_key)
        if normalized_access_key and normalized_secret_key:
            client_kwargs['aws_access_key_id'] = normalized_access_key
            client_kwargs['aws_secret_access_key'] = normalized_secret_key

        config_kwargs: dict[str, Any] = {
            'connect_timeout': max(int(connect_timeout_seconds), 1),
            'read_timeout': max(int(read_timeout_seconds), 1),
            'retries': {
                'total_max_attempts': max(int(max_attempts), 1),
                'mode': 'standard',
            },
        }
        if force_path_style:
            config_kwargs['s3'] = {'addressing_style': 'path'}
        client_kwargs['config'] = BotoCoreConfig(**config_kwargs)

        self.client = boto3.client('s3', **client_kwargs)
        self._client_error = ClientError

    def save_file(
        self,
        source_path: Path,
        object_key: str,
        *,
        content_type: str = 'application/octet-stream',
        metadata: Mapping[str, str] | None = None,
    ) -> StoredArtifact:
        final_key = self._build_key(object_key)
        upload_args: dict[str, Any] = {'ContentType': content_type}
        if metadata:
            upload_args['Metadata'] = {str(key): str(value) for key, value in metadata.items()}

        self.client.upload_file(
            str(source_path),
            self.bucket,
            final_key,
            ExtraArgs=upload_args,
        )

        return StoredArtifact(
            backend=self.backend_name,
            object_key=final_key,
            uri=f'{self.backend_name}:{final_key}',
            size_bytes=source_path.stat().st_size,
            content_type=content_type,
            metadata=dict(metadata or {}),
        )

    def build_download_path(
        self,
        object_key: str,
    ) -> Path:
        cache_path = self._resolve_cache_path(object_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, object_key, str(cache_path))
        return cache_path

    def exists(
        self,
        object_key: str,
    ) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except self._client_error as exc:
            error_code = str(exc.response.get('Error', {}).get('Code') or '')
            if error_code in {'404', 'NoSuchKey', 'NotFound'}:
                return False
            raise

    def stat(
        self,
        object_key: str,
    ) -> ArtifactStat:
        response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        return ArtifactStat(
            backend=self.backend_name,
            object_key=object_key,
            size_bytes=int(response.get('ContentLength') or 0),
            content_type=response.get('ContentType'),
            etag=str(response.get('ETag') or '').strip('"') or None,
            metadata=dict(response.get('Metadata') or {}),
        )

    def delete(
        self,
        object_key: str,
    ) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def test_connection(self) -> bool:
        self.client.head_bucket(Bucket=self.bucket)
        return True

    def _build_key(
        self,
        object_key: str,
    ) -> str:
        clean_key = object_key.strip().lstrip('/').replace('\\', '/')
        if not clean_key:
            raise ValueError('Artifact storage object key is empty.')
        if not self.prefix or clean_key.startswith(f'{self.prefix}/'):
            return clean_key
        return f'{self.prefix}/{clean_key}'

    def _resolve_cache_path(
        self,
        object_key: str,
    ) -> Path:
        clean_key = object_key.strip().lstrip('/').replace('\\', '/')
        resolved_path = (self.cache_dir / clean_key).resolve()
        cache_root = self.cache_dir.resolve()
        if cache_root not in resolved_path.parents and resolved_path != cache_root:
            raise ValueError('Invalid S3 artifact download cache object key.')
        return resolved_path


def normalize_optional_string(value: str | None) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def normalize_s3_prefix(prefix: str | None) -> str:
    return str(prefix or '').strip().strip('/')
