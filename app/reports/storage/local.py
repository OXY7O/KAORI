from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flask import current_app

from app.reports.storage.base import StoredReportFile
from app.storage.local import LocalArtifactStorage
from app.storage.service import resolve_app_path


class LocalReportStorage(LocalArtifactStorage):
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


def resolve_configured_path(
    configured_path: str | Path | None,
    default_path: Path,
) -> Path:
    return resolve_app_path(configured_path, default_path)


def build_local_report_storage() -> LocalReportStorage:
    configured_root = current_app.config.get('REPORT_LOCAL_STORAGE_DIR') or current_app.config.get('REPORT_STORAGE_ROOT_DIR')
    root_dir = resolve_configured_path(
        configured_root,
        Path(current_app.instance_path),
    )
    return LocalReportStorage(root_dir=root_dir)
