from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from app.definitions.integration_registry import integration_compatibility_document
from app.definitions.validation import require_mapping, require_str, string_tuple


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


def _load_compatibility_contract() -> tuple[dict[str, str], dict[str, tuple[CompatibilityProfile, ...]]]:
    document = integration_compatibility_document()
    raw_policy = require_mapping(document.get('kubernetes_lifecycle_policy'), 'kubernetes_lifecycle_policy')
    policy = {
        key: require_str(raw_policy, key, 'kubernetes_lifecycle_policy')
        for key in (
            'supported_version_constraint',
            'legacy_min_version',
            'current_min_version',
            'current_max_version_exclusive',
            'current_version_label',
            'supported_version_label',
        )
    }
    grouped: dict[str, list[CompatibilityProfile]] = {}
    for index, raw in enumerate(document.get('profiles') or []):
        item = require_mapping(raw, f'profiles[{index}]')
        product = require_str(item, 'product', f'profiles[{index}]')
        profile = CompatibilityProfile(
            key=require_str(item, 'key', f'profiles[{index}]'),
            product=product,
            version_constraint=require_str(item, 'version_constraint', f'profiles[{index}]'),
            support_level=require_str(item, 'support_level', f'profiles[{index}]'),
            required_capabilities=string_tuple(
                item.get('required_capabilities'),
                f'profiles[{index}].required_capabilities',
            ),
            notes=require_str(item, 'notes', f'profiles[{index}]'),
            query_profile=(str(item.get('query_profile')).strip() if item.get('query_profile') else None),
        )
        grouped.setdefault(product, []).append(profile)
    return policy, {product: tuple(items) for product, items in grouped.items()}


_KUBERNETES_POLICY, PROFILES = _load_compatibility_contract()
PROFILES_BY_KEY = {profile.key: profile for profiles in PROFILES.values() for profile in profiles}
KUBERNETES_SUPPORTED_VERSION_CONSTRAINT = _KUBERNETES_POLICY['supported_version_constraint']
KUBERNETES_LEGACY_MIN_VERSION = Version(_KUBERNETES_POLICY['legacy_min_version'])
KUBERNETES_CURRENT_MIN_VERSION = Version(_KUBERNETES_POLICY['current_min_version'])
KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE = Version(_KUBERNETES_POLICY['current_max_version_exclusive'])
KUBERNETES_CURRENT_VERSION_LABEL = _KUBERNETES_POLICY['current_version_label']
KUBERNETES_SUPPORTED_VERSION_LABEL = _KUBERNETES_POLICY['supported_version_label']


def kubernetes_lifecycle(version: str | None) -> str:
    normalized = normalize_runtime_version(version or '')
    try:
        parsed = Version(normalized)
    except InvalidVersion:
        return 'unknown'
    if KUBERNETES_CURRENT_MIN_VERSION <= parsed < KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE:
        return 'current'
    if KUBERNETES_LEGACY_MIN_VERSION <= parsed < KUBERNETES_CURRENT_MIN_VERSION:
        return 'legacy'
    return 'unknown'


def kubernetes_lifecycle_policy(version: str | None) -> dict[str, str]:
    """Return the source-controlled KAORI Kubernetes lifecycle contract."""
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


def get_profile_by_key(key: str | None) -> CompatibilityProfile | None:
    if not key:
        return None
    return PROFILES_BY_KEY.get(str(key).strip())
