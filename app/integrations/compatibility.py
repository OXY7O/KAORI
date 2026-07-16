from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version


@dataclass(frozen=True)
class CompatibilityProfile:
    key: str
    product: str
    version_constraint: str
    support_level: str
    required_capabilities: tuple[str, ...]
    notes: str
    query_profile: str | None = None

    def matches(self, version: str) -> bool:
        try:
            return Version(normalize_runtime_version(version)) in SpecifierSet(self.version_constraint)
        except InvalidVersion:
            return False


@dataclass(frozen=True)
class CompatibilityResult:
    status: str
    readiness: str
    profile_key: str | None
    support_level: str
    message: str
    detected_version: str | None
    missing_capabilities: tuple[str, ...] = ()


PROFILES: dict[str, tuple[CompatibilityProfile, ...]] = {
    'kubernetes': (
        CompatibilityProfile('kubernetes-legacy-1-20-1-23', 'kubernetes', '>=1.20,<1.24', 'legacy', ('core_v1', 'apps_v1', 'networking_v1'), 'Legacy Kubernetes profile. Feature readiness must be validated from live API discovery and RBAC.'),
        CompatibilityProfile('kubernetes-standard-1-24-1-29', 'kubernetes', '>=1.24,<1.30', 'supported', ('core_v1', 'apps_v1', 'networking_v1', 'storage_v1'), 'Supported Kubernetes profile. Feature readiness remains capability-specific.'),
        CompatibilityProfile('kubernetes-modern-1-30-1-33', 'kubernetes', '>=1.30,<1.34', 'supported', ('core_v1', 'apps_v1', 'networking_v1', 'storage_v1'), 'Modern Kubernetes profile. Validate removed APIs and feature permissions before activation.'),
        CompatibilityProfile('kubernetes-current-1-34-1-36', 'kubernetes', '>=1.34,<1.37', 'current', ('core_v1', 'apps_v1', 'networking_v1', 'storage_v1'), 'Current Kubernetes profile. Live API discovery is required before KAORI enables each feature.'),
    ),
    'prometheus': (
        CompatibilityProfile('prometheus-v2-kubernetes-v1', 'prometheus', '>=2.40,<3.0', 'legacy_supported', ('instant_query', 'range_query'), 'Prometheus 2.x profile using HTTP API v1 and the versioned Kubernetes PromQL pack.', 'promql-kubernetes-v2'),
        CompatibilityProfile('prometheus-v3-kubernetes-v1', 'prometheus', '>=3.0,<4.0', 'current', ('instant_query', 'range_query'), 'Prometheus 3.x profile. Query, metric, and label-schema validation is required before runtime use.', 'promql-kubernetes-v3'),
    ),
    'alertmanager': (
        CompatibilityProfile('alertmanager-v2-legacy', 'alertmanager', '>=0.25,<0.27', 'legacy', ('status_v2', 'alerts_v2', 'silences_v2'), 'Legacy Alertmanager profile. KAORI uses API v2 only; API v1 is never used.'),
        CompatibilityProfile('alertmanager-v2-current', 'alertmanager', '>=0.27,<0.34', 'current', ('status_v2', 'alerts_v2', 'silences_v2'), 'Current Alertmanager API v2 profile.'),
    ),
    'thanos': (
        CompatibilityProfile('thanos-query-v0-39', 'thanos', '>=0.39,<0.40', 'supported', ('prometheus_api_v1', 'instant_query', 'range_query'), 'Supported Thanos Query 0.39 profile.'),
        CompatibilityProfile('thanos-query-v0-40', 'thanos', '>=0.40,<0.41', 'supported', ('prometheus_api_v1', 'instant_query', 'range_query'), 'Supported Thanos Query 0.40 profile.'),
        CompatibilityProfile('thanos-query-v0-41', 'thanos', '>=0.41,<0.42', 'current', ('prometheus_api_v1', 'instant_query', 'range_query'), 'Current Thanos Query profile.'),
    ),
}


def evaluate_compatibility(product: str, version: str | None, capabilities: Iterable[str] = ()) -> CompatibilityResult:
    product_key = product.strip().lower()
    raw = (version or '').strip() or None
    detected = normalize_runtime_version(raw) if raw else None
    if not detected or detected.lower() == 'unknown':
        return CompatibilityResult('version_unknown', 'blocked', None, 'unknown', 'The endpoint responded, but KAORI could not determine a supported runtime version.', detected)
    profile = next((item for item in PROFILES.get(product_key, ()) if item.matches(detected)), None)
    if profile is None:
        return CompatibilityResult('unsupported_version', 'blocked', None, 'blocked', f'{product.title()} {detected} has no KAORI compatibility profile. Integration activation is blocked.', detected)
    observed = set(capabilities)
    missing = tuple(item for item in profile.required_capabilities if item not in observed)
    if missing:
        return CompatibilityResult('capability_mismatch', 'blocked', profile.key, profile.support_level, 'Required API capabilities are missing: ' + ', '.join(missing), detected, missing)
    warning = profile.support_level in {'legacy', 'deprecated', 'legacy_supported'}
    return CompatibilityResult('compatible_with_warnings' if warning else 'compatible', 'degraded' if warning else 'ready', profile.key, profile.support_level, profile.notes, detected)


def normalize_runtime_version(value: str) -> str:
    raw = value.strip()
    match = re.search(r'v?(\d+\.\d+(?:\.\d+)?)', raw, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return raw.lower().lstrip('v').split('+', 1)[0].split('-', 1)[0]


def get_profile(product: str, key: str | None) -> CompatibilityProfile | None:
    if not key:
        return None
    return next((profile for profile in PROFILES.get(product, ()) if profile.key == key), None)
