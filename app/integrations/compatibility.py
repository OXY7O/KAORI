from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

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


KUBERNETES_SUPPORTED_VERSION_CONSTRAINT = '>=1.20,<2.0'
KUBERNETES_CURRENT_MIN_VERSION = Version('1.34')
KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE = Version('1.37')
KUBERNETES_CURRENT_VERSION_LABEL = 'v1.34–v1.36'
KUBERNETES_SUPPORTED_VERSION_LABEL = 'v1.20–v1.x'


PROFILES: dict[str, tuple[CompatibilityProfile, ...]] = {
    'kubernetes': (
        CompatibilityProfile(
            'kubernetes-api-v1',
            'kubernetes',
            KUBERNETES_SUPPORTED_VERSION_CONSTRAINT,
            'supported',
            (),
            'KAORI Kubernetes API contract v1. Live API discovery and feature-level RBAC determine readiness.',
        ),
    ),
    'prometheus': (
        CompatibilityProfile(
            'prometheus-http-v2',
            'prometheus',
            '>=2.40,<3.0',
            'legacy_supported',
            ('instant_query', 'range_query'),
            'Prometheus HTTP API profile for runtime major 2.',
            'promql-kubernetes-v1',
        ),
        CompatibilityProfile(
            'prometheus-http-v3',
            'prometheus',
            '>=3.0,<4.0',
            'current',
            ('instant_query', 'range_query'),
            'Prometheus HTTP API profile for runtime major 3.',
            'promql-kubernetes-v1',
        ),
    ),
    'alertmanager': (
        CompatibilityProfile(
            'alertmanager-api-v2-legacy',
            'alertmanager',
            '>=0.25,<0.27',
            'legacy',
            ('status_v2', 'alerts_v2', 'silences_v2'),
            'Legacy runtime line using Alertmanager API v2 only.',
        ),
        CompatibilityProfile(
            'alertmanager-api-v2-current',
            'alertmanager',
            '>=0.27,<0.34',
            'current',
            ('status_v2', 'alerts_v2', 'silences_v2'),
            'Current Alertmanager API v2 profile.',
        ),
    ),
    'thanos': (
        CompatibilityProfile(
            'thanos-query-v0-39',
            'thanos',
            '>=0.39,<0.40',
            'supported',
            ('prometheus_api_v1', 'instant_query', 'range_query'),
            'Supported Thanos Query 0.39 profile.',
        ),
        CompatibilityProfile(
            'thanos-query-v0-40',
            'thanos',
            '>=0.40,<0.41',
            'supported',
            ('prometheus_api_v1', 'instant_query', 'range_query'),
            'Supported Thanos Query 0.40 profile.',
        ),
        CompatibilityProfile(
            'thanos-query-v0-41',
            'thanos',
            '>=0.41,<0.42',
            'current',
            ('prometheus_api_v1', 'instant_query', 'range_query'),
            'Current Thanos Query profile.',
        ),
    ),
}


def kubernetes_lifecycle(version: str | None) -> str:
    normalized = normalize_runtime_version(version or '')
    try:
        parsed = Version(normalized)
    except InvalidVersion:
        return 'unknown'
    if KUBERNETES_CURRENT_MIN_VERSION <= parsed < KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE:
        return 'current'
    if Version('1.20') <= parsed < KUBERNETES_CURRENT_MIN_VERSION:
        return 'legacy'
    return 'unknown'


def kubernetes_lifecycle_policy(version: str | None) -> dict[str, str]:
    """Return the KAORI version-lifecycle contract shown to operators.

    The current band is an explicit KAORI support policy, not a claim about the
    upstream Kubernetes support calendar. Keeping it centralized prevents runtime,
    validation, and history views from presenting different accepted ranges.
    """
    detected = normalize_runtime_version(version or '') or 'unknown'
    lifecycle = kubernetes_lifecycle(detected)
    return {
        'detected_version': f'v{detected}' if detected != 'unknown' else 'Unknown',
        'lifecycle_status': lifecycle,
        'current_version_band': KUBERNETES_CURRENT_VERSION_LABEL,
        'supported_version_band': KUBERNETES_SUPPORTED_VERSION_LABEL,
        'supported_constraint': KUBERNETES_SUPPORTED_VERSION_CONSTRAINT,
        'policy_label': 'KAORI Kubernetes lifecycle policy',
    }


def evaluate_compatibility(product: str, version: str | None, capabilities: Iterable[str] = ()) -> CompatibilityResult:
    product_key = product.strip().lower()
    raw = (version or '').strip() or None
    detected = normalize_runtime_version(raw) if raw else None
    if not detected or detected.lower() == 'unknown':
        return CompatibilityResult(
            'version_unknown',
            'blocked',
            None,
            'unknown',
            'The endpoint responded, but KAORI could not determine a supported runtime version.',
            detected,
        )
    profile = next((item for item in PROFILES.get(product_key, ()) if item.matches(detected)), None)
    if profile is None:
        return CompatibilityResult(
            'unsupported_version',
            'blocked',
            None,
            'blocked',
            f'{product.title()} {detected} has no KAORI compatibility profile. Integration activation is blocked.',
            detected,
        )
    observed = set(capabilities)
    missing = tuple(item for item in profile.required_capabilities if item not in observed)
    if missing:
        return CompatibilityResult(
            'capability_mismatch',
            'blocked',
            profile.key,
            profile.support_level,
            'Required API capabilities are missing: ' + ', '.join(missing),
            detected,
            missing,
        )
    warning = profile.support_level in {'legacy', 'deprecated', 'legacy_supported'}
    return CompatibilityResult(
        'compatible_with_warnings' if warning else 'compatible',
        'degraded' if warning else 'ready',
        profile.key,
        profile.support_level,
        profile.notes,
        detected,
    )


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
