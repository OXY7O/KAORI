from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class RegistryVulnerabilityEvidence:
    finding_key: str
    vulnerability_id: str
    severity: str
    package: str | None = None
    installed_version: str | None = None
    fixed_version: str | None = None
    fix_available: bool = False
    cvss_score: str | None = None
    description: str | None = None
    links: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryArtifactSecurityEvidence:
    artifact_id: int
    vulnerability_state: str
    scan_status: str
    scan_severity: str | None = None
    scanner_name: str | None = None
    scanner_vendor: str | None = None
    scanner_version: str | None = None
    scan_started_at: datetime | None = None
    scan_completed_at: datetime | None = None
    signature_state: str = 'not_collected'
    signature_count: int = 0
    trust_state: str = 'not_evaluated'
    sbom_state: str = 'not_collected'
    sbom_count: int = 0
    findings: tuple[RegistryVulnerabilityEvidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistrySecurityEvidence:
    provider_key: str
    integration_instance_id: int
    observed_at: datetime
    vulnerability_capability_state: str
    signature_capability_state: str
    sbom_capability_state: str
    artifacts: tuple[RegistryArtifactSecurityEvidence, ...]
