from __future__ import annotations

import shutil
from pathlib import Path

from flask import current_app

from app.reports.storage.base import StoredReportFile


class LocalReportStorage:
    backend_name = 'local'

    def __init__(
        self,
        root_dir: Path,
    ) -> None:
        self.root_dir = root_dir

    def save_file(
        self,
        source_path: Path,
        object_key: str,
    ) -> StoredReportFile:
        destination_path = self._resolve_object_key(
            object_key,
        )
        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_path,
            destination_path,
        )

        size_bytes = destination_path.stat().st_size

        return StoredReportFile(
            backend=self.backend_name,
            object_key=object_key,
            uri=f'{self.backend_name}:{object_key}',
            size_bytes=size_bytes,
        )

    def build_download_path(
        self,
        object_key: str,
    ) -> Path:
        return self._resolve_object_key(
            object_key,
        )

    def exists(
        self,
        object_key: str,
    ) -> bool:
        return self._resolve_object_key(
            object_key,
        ).exists()

    def delete(
        self,
        object_key: str,
    ) -> None:
        file_path = self._resolve_object_key(
            object_key,
        )

        if file_path.exists():
            file_path.unlink()

    def _resolve_object_key(
        self,
        object_key: str,
    ) -> Path:
        clean_key = object_key.strip().lstrip('/').replace('\\', '/')
        resolved_path = (self.root_dir / clean_key).resolve()
        root_path = self.root_dir.resolve()

        if root_path not in resolved_path.parents and resolved_path != root_path:
            raise ValueError(
                'Invalid report storage object key.',
            )

        return resolved_path


def resolve_configured_path(
    configured_path: str | Path | None,
    default_path: Path,
) -> Path:
    if configured_path:
        resolved_path = Path(
            configured_path,
        )
    else:
        resolved_path = default_path

    if not resolved_path.is_absolute():
        resolved_path = (
            Path(
                current_app.root_path,
            ).parent
            / resolved_path
        )

    return resolved_path


def build_local_report_storage() -> LocalReportStorage:
    configured_root = current_app.config.get(
        'REPORT_LOCAL_STORAGE_DIR',
    ) or current_app.config.get(
        'REPORT_STORAGE_ROOT_DIR',
    )

    root_dir = resolve_configured_path(
        configured_root,
        Path(
            current_app.instance_path,
        ),
    )

    return LocalReportStorage(
        root_dir=root_dir,
    )
