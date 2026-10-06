from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict


class MinioConnectionError(RuntimeError):
    pass


InventoryProgressCallback = Callable[[int, int, str], None]


if TYPE_CHECKING:
    from app.integrations.storage.object_storage.providers.minio.client import MinioBucketSummary


@dataclass(frozen=True, slots=True)
class MinioQuotaEvidence:
    quota_bytes: int | None
    state: str
    code: str
    source: str
    checked_at: datetime
    status_code: int | None = None
    provider_code: str | None = None


@dataclass(frozen=True, slots=True)
class MinioUsageEvidence:
    buckets: dict[str, tuple[int, int]]
    state: str
    code: str
    source: str
    checked_at: datetime
    observed_at: datetime | None = None
    status_code: int | None = None
    provider_code: str | None = None


@dataclass(frozen=True, slots=True)
class MinioConnectionResult:
    connected: bool
    latency_ms: int
    bucket_count: int
    bucket_names: tuple[str, ...]
    server_header: str | None
    deployment_id: str | None
    product: str
    identity_evidence: str
    bucket_inventory: tuple[MinioBucketSummary, ...] = ()


@dataclass(frozen=True, slots=True)
class MinioInventoryResult:
    latency_ms: int
    buckets: tuple[MinioBucketSummary, ...]
    warning_count: int = 0
    usage_stats_mode: str = 'disabled'


@dataclass(frozen=True, slots=True)
class MinioRuntimeProbeResult:
    connected: bool
    latency_ms: int
    status_code: int
    probe: str


@dataclass(frozen=True, slots=True)
class MinioInventoryConnection:
    endpoint: str
    access_key: str
    secret_key: str
    region: str
    timeout: int
    verify_ssl: bool


class MinioInventoryOptions(TypedDict, total=False):
    collect_quota: bool
    collect_usage_stats: bool
    usage_stats_mode: str | None
    progress_callback: InventoryProgressCallback | None
