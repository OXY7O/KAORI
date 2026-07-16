from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version


PROMQL_KUBERNETES_PROFILE = 'promql-kubernetes-v1'
ALERT_MANAGEMENT_PROFILE = 'alert-management-v1'
KUBERNETES_API_PROFILE = 'kubernetes-api-v1'


@dataclass(frozen=True)
class CompatibilityProfile:
    key: str
    product: str
    version_constraint: str
    support_level: str
    required_capabilities: tuple[str, ...]
    notes: str

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


@dataclass(frozen=True)
class KubernetesLifecycleResult:
    status: str
    message: str


PROFILES: dict[str, tuple[CompatibilityProfile, ...]] = {
    'kubernetes': (
        CompatibilityProfile(
            KUBERNETES_API_PROFILE,
            'kubernetes',
            '>=1.20,<1.37',
            'supported',
            ('core_v1', 'apps_v1', 'networking_v1', 'storage_v1'),
            'Kubernetes API contract v1. Feature readiness is determined from live API discovery and RBAC, not the version string alone.',
        ),
    ),
    'prometheus': (
        CompatibilityProfile(
            'prometheus-http-v2',
            'prometheus',
            '>=2.40,<3.0',
            'legacy_supported',
            ('instant_query', 'range_query'),
            'Prometheus HTTP compatibility profile for runtime major 2.',
        ),
        CompatibilityProfile(
            'prometheus-http-v3',
            'prometheus',
            '>=3.0,<4.0',
            'current',
            ('instant_query', 'range_query'),
            'Prometheus HTTP compatibility profile for runtime major 3.',
        ),
    ),
    'alertmanager': (
        CompatibilityProfile(
            'alertmanager-api-v2-legacy',
            'alertmanager',
            '>=0.25,<0.27',
            'legacy',
            ('status_v2', 'alerts_v2', 'silences_v2'),
            'Legacy Alertmanager runtime using the API v2 contract. API v1 is never used.',
        ),
        CompatibilityProfile(
            'alertmanager-api-v2-current',
            'alertmanager',
            '>=0.27,<0.34',
            'current',
            ('status_v2', 'alerts_v2', 'silences_v2'),
            'Current Alertmanager runtime using the API v2 contract.',
        ),
    ),
    'thanos': (
        CompatibilityProfile('thanos-query-v0-39', 'thanos', '>=0.39,<0.40', 'supported', ('prometheus_api_v1', 'instant_query', 'range_query'), 'Supported Thanos Query 0.39 endpoint profile.'),
        CompatibilityProfile('thanos-query-v0-40', 'thanos', '>=0.40,<0.41', 'supported', ('prometheus_api_v1', 'instant_query', 'range_query'), 'Supported Thanos Query 0.40 endpoint profile.'),
        CompatibilityProfile('thanos-query-v0-41', 'thanos', '>=0.41,<0.42', 'current', ('prometheus_api_v1', 'instant_query', 'range_query'), 'Current Thanos Query endpoint profile.'),
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


def get_kubernetes_lifecycle(version: str | None) -> KubernetesLifecycleResult:
    """Return release-lifecycle posture separately from API compatibility.

    The supported release window is intentionally centralized here so updating the
    lifecycle policy does not require creating a new API compatibility profile.
    """
    normalized = normalize_runtime_version(version or '')
    try:
        parsed = Version(normalized)
    except InvalidVersion:
        return KubernetesLifecycleResult('unknown', 'KAORI could not determine the Kubernetes release lifecycle.')
    if parsed in SpecifierSet('>=1.34,<1.37'):
        return KubernetesLifecycleResult('current', 'The Kubernetes minor release is within the current KAORI lifecycle window.')
    if parsed in SpecifierSet('>=1.20,<1.34'):
        return KubernetesLifecycleResult('legacy', 'The Kubernetes API contract is supported, but this minor release is outside the current lifecycle window.')
    return KubernetesLifecycleResult('unknown', 'This Kubernetes minor release is outside the lifecycle matrix currently maintained by KAORI.')


def prometheus_major_for_profile(profile_key: str | None) -> str | None:
    return {
        'prometheus-http-v2': '2',
        'prometheus-http-v3': '3',
    }.get(profile_key or '')


def prometheus_profile_for_major(major: str | int | None) -> CompatibilityProfile | None:
    key = {
        '2': 'prometheus-http-v2',
        '3': 'prometheus-http-v3',
    }.get(str(major or '').strip())
    return get_profile('prometheus', key)


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
