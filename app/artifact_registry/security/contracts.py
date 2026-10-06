from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
SUCCESSFUL_REGISTRY_SCAN_STATUSES = frozenset({'success', 'finished', 'completed'})


def registry_scan_evidence_ready(value: str | None) -> bool:
    return str(value or '').strip().lower() in SUCCESSFUL_REGISTRY_SCAN_STATUSES


@dataclass(frozen=True, slots=True)
class RegistrySecurityTarget:
    """Stable committed artifact identity consumed by provider security collectors."""

    artifact_id: int
    project_name: str
    repository_name: str
    digest: str
    scan_status: str | None
    scan_completed_at: datetime | None
    vulnerability_summary: dict[str, int]
    signature_status: str | None
    sbom_status: str | None
    has_scan_snapshot: bool


@dataclass(slots=True)
class RegistryArtifactSecurityEvidence:
    artifact_id: int
    scan_status: str | None
    scan_completed_at: datetime | None
    vulnerability_summary: dict[str, int] = field(default_factory=dict)
    signature_status: str | None = None
    sbom_status: str | None = None
    scan_snapshot: dict[str, Any] | None = None
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)
    reuse_existing_scan: bool = False
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RegistrySecurityEvidence:
    artifacts: list[RegistryArtifactSecurityEvidence] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
