from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Iterator, Protocol


@dataclass(frozen=True)
class RetentionPolicy:
    domain: str
    enabled: bool
    retention_days: int
    archive_retention_days: int
    batch_size: int
    protect_unreviewed: bool = False
    protected_max_days: int | None = None


@dataclass(frozen=True)
class ArchiveBoundary:
    cutoff_at: datetime
    maximum_record_id: int | None
    record_count: int
    range_start: datetime | None
    range_end: datetime | None
    protected_record_count: int = 0
    protected_cutoff_at: datetime | None = None


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
