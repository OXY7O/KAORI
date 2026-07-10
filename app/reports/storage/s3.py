from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from app.reports.storage.base import StoredReportFile


class S3ReportStorage:
    backend_name = 's3'

    def __init__(
        self,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        prefix: str | None = None,
        force_path_style: bool = False,
    ) -> None:
        if not bucket:
            raise RuntimeError(
                'REPORT_S3_BUCKET is required when REPORT_STORAGE_BACKEND=s3.',
            )

        try:
            import boto3  # type: ignore[import-not-found]
            from botocore.config import Config as BotoCoreConfig  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                'boto3 is required for S3-compatible report storage. Install it with: pip install boto3',
            ) from exc

        self.bucket = bucket
        self.prefix = normalize_s3_prefix(
            prefix,
        )

        client_kwargs: dict[str, Any] = {
            'region_name': region or 'us-east-1',
        }

        normalized_endpoint_url = normalize_optional_string(
            endpoint_url,
        )
        if normalized_endpoint_url:
            client_kwargs['endpoint_url'] = normalized_endpoint_url

        normalized_access_key_id = normalize_optional_string(
            access_key_id,
        )
        normalized_secret_access_key = normalize_optional_string(
            secret_access_key,
        )

        if normalized_access_key_id and normalized_secret_access_key:
            client_kwargs['aws_access_key_id'] = normalized_access_key_id
            client_kwargs['aws_secret_access_key'] = normalized_secret_access_key

        if force_path_style:
            client_kwargs['config'] = BotoCoreConfig(
                s3={
                    'addressing_style': 'path',
                }
            )

        self.client = boto3.client(
            's3',
            **client_kwargs,
        )

    def save_file(
        self,
        source_path: Path,
        object_key: str,
    ) -> StoredReportFile:
        final_key = self._build_key(
            object_key,
        )

        self.client.upload_file(
            str(
                source_path,
            ),
            self.bucket,
            final_key,
            ExtraArgs={
                'ContentType': 'application/pdf',
            },
        )

        return StoredReportFile(
            backend=self.backend_name,
            object_key=final_key,
            uri=f'{self.backend_name}:{final_key}',
            size_bytes=source_path.stat().st_size,
        )

    def build_download_path(
        self,
        object_key: str,
    ) -> Path:
        cache_path = build_s3_download_cache_path(
            object_key,
        )
        cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client.download_file(
            self.bucket,
            object_key,
            str(
                cache_path,
            ),
        )

        return cache_path

    def exists(
        self,
        object_key: str,
    ) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=object_key,
            )
            return True
        except Exception:
            return False

    def delete(
        self,
        object_key: str,
    ) -> None:
        self.client.delete_object(
            Bucket=self.bucket,
            Key=object_key,
        )

    def test_connection(self) -> bool:
        self.client.head_bucket(
            Bucket=self.bucket,
        )
        return True

    def _build_key(
        self,
        object_key: str,
    ) -> str:
        clean_key = object_key.strip().lstrip('/').replace('\\', '/')

        if not self.prefix:
            return clean_key

        if clean_key.startswith(
            f'{self.prefix}/',
        ):
            return clean_key

        return f'{self.prefix}/{clean_key}'


def normalize_optional_string(
    value: str | None,
) -> str | None:
    text = str(
        value or '',
    ).strip()

    return text or None


def normalize_s3_prefix(
    prefix: str | None,
) -> str:
    return (
        str(
            prefix or '',
        )
        .strip()
        .strip('/')
    )


def get_report_download_cache_dir() -> Path:
    configured_cache_dir = current_app.config.get(
        'REPORT_DOWNLOAD_CACHE_DIR',
        'instance/report-download-cache',
    )

    cache_root = Path(
        configured_cache_dir,
    )

    if not cache_root.is_absolute():
        cache_root = (
            Path(
                current_app.root_path,
            ).parent
            / cache_root
        )

    return cache_root


def build_s3_download_cache_path(
    object_key: str,
) -> Path:
    safe_key = object_key.strip().lstrip('/').replace('\\', '/')
    cache_root = get_report_download_cache_dir()

    resolved_path = (cache_root / safe_key).resolve()
    resolved_cache_root = cache_root.resolve()

    if resolved_cache_root not in resolved_path.parents and resolved_path != resolved_cache_root:
        raise ValueError(
            'Invalid S3 report download cache object key.',
        )

    return resolved_path


def parse_bool_config(
    value: object,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    return str(
        value or '',
    ).strip().lower() in {
        '1',
        'true',
        'yes',
        'on',
    }


def build_s3_report_storage() -> S3ReportStorage:
    return S3ReportStorage(
        bucket=str(
            current_app.config.get(
                'REPORT_S3_BUCKET',
                '',
            )
            or ''
        ),
        region=current_app.config.get(
            'REPORT_S3_REGION',
            'us-east-1',
        ),
        endpoint_url=current_app.config.get(
            'REPORT_S3_ENDPOINT_URL',
        ),
        access_key_id=current_app.config.get(
            'REPORT_S3_ACCESS_KEY_ID',
        ),
        secret_access_key=current_app.config.get(
            'REPORT_S3_SECRET_ACCESS_KEY',
        ),
        prefix=current_app.config.get(
            'REPORT_S3_PREFIX',
            '',
        ),
        force_path_style=parse_bool_config(
            current_app.config.get(
                'REPORT_S3_FORCE_PATH_STYLE',
                False,
            )
        ),
    )
