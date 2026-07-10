from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredReportFile:
    backend: str
    object_key: str
    uri: str
    size_bytes: int


class ReportStorageBackend(Protocol):
    backend_name: str

    def save_file(
        self,
        source_path: Path,
        object_key: str,
    ) -> StoredReportFile: ...

    def build_download_path(
        self,
        object_key: str,
    ) -> Path: ...

    def exists(
        self,
        object_key: str,
    ) -> bool: ...

    def delete(
        self,
        object_key: str,
    ) -> None: ...
