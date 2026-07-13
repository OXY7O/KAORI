from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from typing import Mapping

from app.storage.base import ArtifactStat, StoredArtifact


class LocalArtifactStorage:
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
        *,
        content_type: str = 'application/octet-stream',
        metadata: Mapping[str, str] | None = None,
    ) -> StoredArtifact:
        destination_path = self._resolve_object_key(object_key)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

        return StoredArtifact(
            backend=self.backend_name,
            object_key=self._normalize_object_key(object_key),
            uri=f'{self.backend_name}:{self._normalize_object_key(object_key)}',
            size_bytes=destination_path.stat().st_size,
            content_type=content_type,
            metadata=dict(metadata or {}),
        )

    def build_download_path(
        self,
        object_key: str,
    ) -> Path:
        return self._resolve_object_key(object_key)

    def exists(
        self,
        object_key: str,
    ) -> bool:
        return self._resolve_object_key(object_key).is_file()

    def stat(
        self,
        object_key: str,
    ) -> ArtifactStat:
        file_path = self._resolve_object_key(object_key)
        file_stat = file_path.stat()
        guessed_type, _ = mimetypes.guess_type(file_path.name)

        return ArtifactStat(
            backend=self.backend_name,
            object_key=self._normalize_object_key(object_key),
            size_bytes=file_stat.st_size,
            content_type=guessed_type,
        )

    def delete(
        self,
        object_key: str,
    ) -> None:
        file_path = self._resolve_object_key(object_key)
        if file_path.exists():
            file_path.unlink()

    @staticmethod
    def _normalize_object_key(
        object_key: str,
    ) -> str:
        clean_key = object_key.strip().lstrip('/').replace('\\', '/')
        if not clean_key:
            raise ValueError('Artifact storage object key is empty.')
        return clean_key

    def _resolve_object_key(
        self,
        object_key: str,
    ) -> Path:
        clean_key = self._normalize_object_key(object_key)
        resolved_path = (self.root_dir / clean_key).resolve()
        root_path = self.root_dir.resolve()

        if root_path not in resolved_path.parents and resolved_path != root_path:
            raise ValueError('Invalid artifact storage object key.')

        return resolved_path
