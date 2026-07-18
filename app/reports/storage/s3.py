from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flask import current_app

from app.reports.storage.base import StoredReportFile
from app.storage.s3 import S3ArtifactStorage, normalize_optional_string, normalize_s3_prefix
from app.storage.service import parse_bool_config, resolve_app_path


class S3ReportStorage(S3ArtifactStorage):
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
        super().__init__(
            bucket=bucket,
            cache_dir=get_report_download_cache_dir(),
            region=region,
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            prefix=prefix,
            force_path_style=force_path_style,
        )

    def save_file(
        self,
        source_path: Path,
        object_key: str,
        *,
        content_type: str = 'application/pdf',
        metadata: Mapping[str, str] | None = None,
    ) -> StoredReportFile:
        report_metadata = {'artifact-kind': 'report', **dict(metadata or {})}
        return super().save_file(
            source_path,
            object_key,
            content_type=content_type,
            metadata=report_metadata,
        )


def get_report_download_cache_dir() -> Path:
    return resolve_app_path(
        current_app.config.get('REPORT_DOWNLOAD_CACHE_DIR', 'instance/report-download-cache'),
        Path(current_app.instance_path) / 'report-download-cache',
    )


def build_s3_download_cache_path(
    object_key: str,
) -> Path:
    safe_key = object_key.strip().lstrip('/').replace('\\', '/')
    cache_root = get_report_download_cache_dir()
    resolved_path = (cache_root / safe_key).resolve()
    if cache_root.resolve() not in resolved_path.parents and resolved_path != cache_root.resolve():
        raise ValueError('Invalid S3 report download cache object key.')
    return resolved_path


def build_s3_report_storage() -> S3ReportStorage:
    return S3ReportStorage(
        bucket=str(current_app.config.get('REPORT_S3_BUCKET', '') or ''),
        region=current_app.config.get('REPORT_S3_REGION', 'us-east-1'),
        endpoint_url=current_app.config.get('REPORT_S3_ENDPOINT_URL'),
        access_key_id=current_app.config.get('REPORT_S3_ACCESS_KEY_ID'),
        secret_access_key=current_app.config.get('REPORT_S3_SECRET_ACCESS_KEY'),
        prefix=current_app.config.get('REPORT_S3_PREFIX', ''),
        force_path_style=parse_bool_config(current_app.config.get('REPORT_S3_FORCE_PATH_STYLE', False)),
    )


__all__ = [
    'S3ReportStorage',
    'build_s3_download_cache_path',
    'build_s3_report_storage',
    'get_report_download_cache_dir',
    'normalize_optional_string',
    'normalize_s3_prefix',
    'parse_bool_config',
]
