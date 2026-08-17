from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class RetentionPolicy:
    domain: str
    enabled: bool
    retention_days: int
    archive_retention_days: int
    batch_size: int
    protect_unreviewed: bool = False
    protected_max_days: int | None = None
    settings: dict[str, Any] | None = None


@dataclass(frozen=True)
class ArchiveBoundary:
    selected_at: datetime
    cutoff_at: datetime
    maximum_record_id: int | None
    record_count: int
    range_start: datetime | None
    range_end: datetime | None
    protected_record_count: int = 0
    protected_cutoff_at: datetime | None = None


@dataclass(frozen=True)
class ArchiveSupplement:
    """One binary or auxiliary artifact copied into a lifecycle archive bundle."""

    record_id: Any
    source_path: Path
    relative_path: str
    content_type: str = 'application/octet-stream'
    metadata: dict[str, str] | None = None


class PartialCleanupError(RuntimeError):
    def __init__(self, message: str, deleted_count: int) -> None:
        super().__init__(message)
        self.deleted_count = deleted_count


class ArchiveDomain(Protocol):
    name: str
    source_model: str
    schema_version: int

    def build_policy(self) -> RetentionPolicy: ...

    def inspect_boundary(
        self,
        policy: RetentionPolicy,
    ) -> ArchiveBoundary: ...

    def iter_records(
        self,
        boundary: ArchiveBoundary,
        policy: RetentionPolicy,
    ) -> Iterator[dict[str, Any]]: ...

    def cleanup_records(
        self,
        record_ids: Iterable[Any],
        policy: RetentionPolicy,
    ) -> int: ...
