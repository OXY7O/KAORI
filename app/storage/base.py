from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredArtifact:
    backend: str
    object_key: str
    uri: str
    size_bytes: int
    content_type: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactStat:
    backend: str
    object_key: str
    size_bytes: int
    content_type: str | None = None
    etag: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


class ArtifactStorageBackend(Protocol):
    backend_name: str

    def save_file(
        self,
        source_path: Path,
        object_key: str,
        *,
        content_type: str = 'application/octet-stream',
        metadata: Mapping[str, str] | None = None,
    ) -> StoredArtifact: ...

    def build_download_path(
        self,
        object_key: str,
    ) -> Path: ...

    def exists(
        self,
        object_key: str,
    ) -> bool: ...

    def stat(
        self,
        object_key: str,
    ) -> ArtifactStat: ...

    def delete(
        self,
        object_key: str,
    ) -> None: ...
