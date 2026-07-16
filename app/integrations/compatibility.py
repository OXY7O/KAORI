from __future__ import annotations

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

    def matches(self, version: str) -> bool:
        try:
            return Version(_normalize_version(version)) in SpecifierSet(self.version_constraint)
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
        CompatibilityProfile(
            key='kubernetes-legacy-v1',
            product='kubernetes',
            version_constraint='>=1.20,<1.24',
            support_level='deprecated',
            required_capabilities=('core_v1', 'apps_v1', 'networking_v1'),
            notes='Legacy cluster profile. Read and mutation capabilities must be validated per API resource.',
        ),
        CompatibilityProfile(
            key='kubernetes-standard-v1',
            product='kubernetes',
            version_constraint='>=1.24,<1.30',
            support_level='supported',
            required_capabilities=('core_v1', 'apps_v1', 'networking_v1', 'storage_v1'),
            notes='Primary KAORI Kubernetes compatibility profile.',
        ),
    ),
    'prometheus': (
        CompatibilityProfile(
            key='prometheus-http-api-v1',
            product='prometheus',
            version_constraint='>=2.0,<3.0',
            support_level='supported',
            required_capabilities=('build_info', 'instant_query', 'range_query'),
            notes='Uses the stable Prometheus HTTP API under /api/v1 and the KAORI PromQL query registry.',
        ),
    ),
    'alertmanager': (
        CompatibilityProfile(
            key='alertmanager-api-v2',
            product='alertmanager',
            version_constraint='>=0.25,<1.0',
            support_level='supported',
            required_capabilities=('status_v2', 'alerts_v2', 'silences_v2'),
            notes='Uses Alertmanager API v2. API v1 is never used by KAORI.',
        ),
    ),
}


def evaluate_compatibility(
    product: str,
    version: str | None,
    capabilities: Iterable[str] = (),
) -> CompatibilityResult:
    normalized_product = product.strip().lower()
    detected = (version or '').strip() or None

    if detected is None or detected.lower() == 'unknown':
        return CompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=None,
            support_level='unknown',
            message='The product responded, but KAORI could not determine a compatible version.',
            detected_version=detected,
        )

    profile = next((item for item in PROFILES.get(normalized_product, ()) if item.matches(detected)), None)
    if profile is None:
        return CompatibilityResult(
            status='unsupported_version',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=f'{product.title()} {detected} does not match a KAORI compatibility profile.',
            detected_version=detected,
        )

    observed = set(capabilities)
    missing = tuple(item for item in profile.required_capabilities if item not in observed)
    if missing:
        return CompatibilityResult(
            status='capability_mismatch',
            readiness='blocked',
            profile_key=profile.key,
            support_level=profile.support_level,
            message='Required API capabilities are missing: ' + ', '.join(missing),
            detected_version=detected,
            missing_capabilities=missing,
        )

    readiness = 'degraded' if profile.support_level == 'deprecated' else 'ready'
    status = 'compatible_with_warnings' if readiness == 'degraded' else 'compatible'
    return CompatibilityResult(
        status=status,
        readiness=readiness,
        profile_key=profile.key,
        support_level=profile.support_level,
        message=profile.notes,
        detected_version=detected,
    )


def _normalize_version(value: str) -> str:
    version = value.strip().lower()
    if version.startswith('v'):
        version = version[1:]
    version = version.split('+', 1)[0]
    version = version.split('-', 1)[0]
    return version
