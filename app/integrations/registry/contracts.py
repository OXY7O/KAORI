from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ArtifactRecord:
    """Provider-neutral normalized OCI artifact evidence."""

    digest: str
    provider_native_id: str | None
    artifact_type: str | None
    media_type: str | None
    size_bytes: int | None
    push_time: datetime | None
    pull_time: datetime | None
    scan_status: str | None = None
    scan_completed_at: datetime | None = None
    vulnerability_summary: dict[str, int] = field(default_factory=dict)
    signature_status: str | None = None
    sbom_status: str | None = None
    scan_snapshot: dict[str, Any] | None = None
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)
    tags: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RepositoryRecord:
    """Provider-neutral normalized repository evidence."""

    name: str
    provider_native_id: str | None
    artifact_count: int | None
    pull_count: int | None
    description: str | None
    provider_created_at: datetime | None
    provider_updated_at: datetime | None
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProjectRecord:
    """Provider-neutral normalized Registry project/namespace evidence."""

    name: str
    provider_native_id: str | None
    public: bool | None
    repository_count: int | None
    repositories: list[RepositoryRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RegistryInventoryEvidence:
    """One provider collector result before KAORI commits normalized state."""

    projects: list[ProjectRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
