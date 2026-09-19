from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from app.definitions.integration_registry import integration_compatibility_document
from app.definitions.validation import require_int, require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True)
class CompatibilityLifecyclePolicy:
    key: str
    version: int
    policy_year: int
    lookback_years: int
    anchor_year: int
    snapshot_date: str
    renewal_cadence: str
    lower_bound_rule: str
    upper_bound_rule: str
    pre_window_posture: str
    future_posture: str
    core_contract_versioning: str

    @property
    def window_label(self) -> str:
        return f'{self.anchor_year}–{self.policy_year}'


@dataclass(frozen=True)
class CompatibilityProfile:
    key: str
    products: tuple[str, ...]
    adapter_key: str
    required_capabilities: tuple[str, ...]
    notes: str
    query_profile: str | None = None

    def supports_product(self, product: str) -> bool:
        return str(product or '').strip().lower() in self.products


@dataclass(frozen=True)
class CompatibilityQualification:
    key: str
    product: str
    version_constraint: str
    contract_profile: str
    support_level: str
    upstream_lifecycle: str
    required_capabilities: tuple[str, ...]
    notes: str

    def matches(self, version: str) -> bool:
        try:
            return Version(normalize_runtime_version(version)) in SpecifierSet(self.version_constraint)
        except InvalidVersion:
            return False


@dataclass(frozen=True)
class CompatibilityProductPolicy:
    key: str
    label: str
    icon: str
    version_scheme: str
    contract_profile: str
    qualification_floor: str
    qualification_ceiling_exclusive: str
    minimum_label: str
    recommended_label: str
    qualified_version_label: str
    upstream_lifecycle_label: str
    support_label: str
    support_tone: str
    capability_summary: str
    validation_basis: str


@dataclass(frozen=True)
class CompatibilityResult:
    status: str
    readiness: str
    profile_key: str | None
    support_level: str
    message: str
    detected_version: str | None
    missing_capabilities: tuple[str, ...] = ()
    qualification_key: str | None = None
    upstream_lifecycle: str = 'unknown'


def _load_compatibility_contract() -> tuple[
    CompatibilityLifecyclePolicy,
    dict[str, str],
    dict[str, CompatibilityProfile],
    dict[str, CompatibilityProductPolicy],
    dict[str, tuple[CompatibilityQualification, ...]],
]:
    document = integration_compatibility_document()
    raw_lifecycle = require_mapping(document.get('lifecycle_policy'), 'lifecycle_policy')
    lifecycle = CompatibilityLifecyclePolicy(
        key=require_str(raw_lifecycle, 'key', 'lifecycle_policy'),
        version=require_int(raw_lifecycle, 'version', 'lifecycle_policy'),
        policy_year=require_int(raw_lifecycle, 'policy_year', 'lifecycle_policy'),
        lookback_years=require_int(raw_lifecycle, 'lookback_years', 'lifecycle_policy'),
        anchor_year=require_int(raw_lifecycle, 'anchor_year', 'lifecycle_policy'),
        snapshot_date=require_str(raw_lifecycle, 'snapshot_date', 'lifecycle_policy'),
        renewal_cadence=require_str(raw_lifecycle, 'renewal_cadence', 'lifecycle_policy'),
        lower_bound_rule=require_str(raw_lifecycle, 'lower_bound_rule', 'lifecycle_policy'),
        upper_bound_rule=require_str(raw_lifecycle, 'upper_bound_rule', 'lifecycle_policy'),
        pre_window_posture=require_str(raw_lifecycle, 'pre_window_posture', 'lifecycle_policy'),
        future_posture=require_str(raw_lifecycle, 'future_posture', 'lifecycle_policy'),
        core_contract_versioning=require_str(raw_lifecycle, 'core_contract_versioning', 'lifecycle_policy'),
    )

    raw_policy = require_mapping(document.get('kubernetes_lifecycle_policy'), 'kubernetes_lifecycle_policy')
    policy = {
        key: require_str(raw_policy, key, 'kubernetes_lifecycle_policy')
        for key in (
            'supported_version_constraint',
            'extended_min_version',
            'current_min_version',
            'current_max_version_exclusive',
            'current_version_label',
            'upstream_supported_version_label',
            'supported_version_label',
            'anchor_release_label',
            'upper_release_label',
        )
    }

    contracts: dict[str, CompatibilityProfile] = {}
    for index, raw in enumerate(require_list(document.get('contract_profiles'), 'contract_profiles')):
        item = require_mapping(raw, f'contract_profiles[{index}]')
        profile = CompatibilityProfile(
            key=require_str(item, 'key', f'contract_profiles[{index}]'),
            products=string_tuple(item.get('products'), f'contract_profiles[{index}].products'),
            adapter_key=require_str(item, 'adapter_key', f'contract_profiles[{index}]'),
            required_capabilities=string_tuple(
                item.get('required_capabilities'),
                f'contract_profiles[{index}].required_capabilities',
            ),
            notes=require_str(item, 'notes', f'contract_profiles[{index}]'),
            query_profile=(str(item.get('query_profile')).strip() if item.get('query_profile') else None),
        )
        contracts[profile.key] = profile

    products: dict[str, CompatibilityProductPolicy] = {}
    for index, raw in enumerate(require_list(document.get('products'), 'products')):
        item = require_mapping(raw, f'products[{index}]')
        policy_item = CompatibilityProductPolicy(
            key=require_str(item, 'key', f'products[{index}]').lower(),
            label=require_str(item, 'label', f'products[{index}]'),
            icon=require_str(item, 'icon', f'products[{index}]'),
            version_scheme=require_str(item, 'version_scheme', f'products[{index}]'),
            contract_profile=require_str(item, 'contract_profile', f'products[{index}]'),
            qualification_floor=require_str(item, 'qualification_floor', f'products[{index}]'),
            qualification_ceiling_exclusive=require_str(
                item,
                'qualification_ceiling_exclusive',
                f'products[{index}]',
            ),
            minimum_label=require_str(item, 'minimum_label', f'products[{index}]'),
            recommended_label=require_str(item, 'recommended_label', f'products[{index}]'),
            qualified_version_label=require_str(item, 'qualified_version_label', f'products[{index}]'),
            upstream_lifecycle_label=require_str(item, 'upstream_lifecycle_label', f'products[{index}]'),
            support_label=require_str(item, 'support_label', f'products[{index}]'),
            support_tone=require_str(item, 'support_tone', f'products[{index}]'),
            capability_summary=require_str(item, 'capability_summary', f'products[{index}]'),
            validation_basis=require_str(item, 'validation_basis', f'products[{index}]'),
        )
        products[policy_item.key] = policy_item

    grouped: dict[str, list[CompatibilityQualification]] = {}
    for index, raw in enumerate(require_list(document.get('qualifications'), 'qualifications')):
        item = require_mapping(raw, f'qualifications[{index}]')
        product = require_str(item, 'product', f'qualifications[{index}]').lower()
        qualification = CompatibilityQualification(
            key=require_str(item, 'key', f'qualifications[{index}]'),
            product=product,
            version_constraint=require_str(item, 'version_constraint', f'qualifications[{index}]'),
            contract_profile=require_str(item, 'contract_profile', f'qualifications[{index}]'),
            support_level=require_str(item, 'support_level', f'qualifications[{index}]'),
            upstream_lifecycle=require_str(item, 'upstream_lifecycle', f'qualifications[{index}]'),
            required_capabilities=string_tuple(
                item.get('required_capabilities'),
                f'qualifications[{index}].required_capabilities',
            ),
            notes=require_str(item, 'notes', f'qualifications[{index}]'),
        )
        grouped.setdefault(product, []).append(qualification)

    return lifecycle, policy, contracts, products, {product: tuple(items) for product, items in grouped.items()}


(
    COMPATIBILITY_LIFECYCLE_POLICY,
    _KUBERNETES_POLICY,
    CONTRACT_PROFILES,
    PRODUCT_POLICIES,
    QUALIFICATIONS,
) = _load_compatibility_contract()
# Backward-compatible import name: these are now version qualification rows, not runtime contract profiles.
PROFILES = QUALIFICATIONS
QUALIFICATIONS_BY_KEY = {
    qualification.key: qualification for qualifications in QUALIFICATIONS.values() for qualification in qualifications
}
KUBERNETES_SUPPORTED_VERSION_CONSTRAINT = _KUBERNETES_POLICY['supported_version_constraint']
KUBERNETES_EXTENDED_MIN_VERSION = Version(_KUBERNETES_POLICY['extended_min_version'])
# Backward-compatible alias for callers that still use the former lifecycle name.
KUBERNETES_LEGACY_MIN_VERSION = KUBERNETES_EXTENDED_MIN_VERSION
KUBERNETES_CURRENT_MIN_VERSION = Version(_KUBERNETES_POLICY['current_min_version'])
KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE = Version(_KUBERNETES_POLICY['current_max_version_exclusive'])
KUBERNETES_CURRENT_VERSION_LABEL = _KUBERNETES_POLICY['current_version_label']
KUBERNETES_UPSTREAM_SUPPORTED_VERSION_LABEL = _KUBERNETES_POLICY['upstream_supported_version_label']
KUBERNETES_SUPPORTED_VERSION_LABEL = _KUBERNETES_POLICY['supported_version_label']


def kubernetes_lifecycle(version: str | None) -> str:
    normalized = normalize_runtime_version(version or '')
    try:
        parsed = Version(normalized)
    except InvalidVersion:
        return 'unknown'
    if KUBERNETES_CURRENT_MIN_VERSION <= parsed < KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE:
        return 'current'
    if KUBERNETES_EXTENDED_MIN_VERSION <= parsed < KUBERNETES_CURRENT_MIN_VERSION:
        return 'extended'
    if parsed < KUBERNETES_EXTENDED_MIN_VERSION:
        return 'end_of_life'
    return 'unknown'


def kubernetes_lifecycle_policy(version: str | None) -> dict[str, str]:
    """Return the source-controlled KAORI Kubernetes lifecycle contract."""
    detected = normalize_runtime_version(version or '') or 'unknown'
    lifecycle = kubernetes_lifecycle(detected)
    return {
        'detected_version': f'v{detected}' if detected != 'unknown' else 'Unknown',
        'lifecycle_status': lifecycle,
        'current_version_band': KUBERNETES_CURRENT_VERSION_LABEL,
        'upstream_supported_version_band': KUBERNETES_UPSTREAM_SUPPORTED_VERSION_LABEL,
        'supported_version_band': KUBERNETES_SUPPORTED_VERSION_LABEL,
        'supported_constraint': KUBERNETES_SUPPORTED_VERSION_CONSTRAINT,
        'policy_label': 'KAORI Kubernetes lifecycle policy',
        'policy_key': COMPATIBILITY_LIFECYCLE_POLICY.key,
        'policy_version': f'v{COMPATIBILITY_LIFECYCLE_POLICY.version}',
        'policy_year': str(COMPATIBILITY_LIFECYCLE_POLICY.policy_year),
        'anchor_year': str(COMPATIBILITY_LIFECYCLE_POLICY.anchor_year),
        'lookback_years': str(COMPATIBILITY_LIFECYCLE_POLICY.lookback_years),
        'window_label': COMPATIBILITY_LIFECYCLE_POLICY.window_label,
        'snapshot_date': COMPATIBILITY_LIFECYCLE_POLICY.snapshot_date,
    }


def evaluate_compatibility(
    product: str,
    version: str | None,
    capabilities: Iterable[str] = (),
) -> CompatibilityResult:
    product_key = str(product or '').strip().lower()
    policy = PRODUCT_POLICIES.get(product_key)
    if policy is None:
        return CompatibilityResult(
            status='unsupported_product',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=f'{product or "Provider"} has no KAORI compatibility contract.',
            detected_version=normalize_runtime_version(version or '') or None,
        )

    contract = CONTRACT_PROFILES[policy.contract_profile]
    raw = (version or '').strip() or None
    detected = normalize_runtime_version(raw) if raw else None
    if not detected or detected.lower() == 'unknown':
        return CompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=contract.key,
            support_level='unknown',
            message=(
                f'{policy.label} responded, but KAORI could not determine a usable runtime version. '
                'Version identity is required before qualification can be evaluated.'
            ),
            detected_version=detected,
        )
    try:
        parsed_version = Version(detected)
    except InvalidVersion:
        return CompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=contract.key,
            support_level='unknown',
            message=f'{policy.label} returned an unparseable runtime version: {detected}.',
            detected_version=detected,
        )

    qualification_floor = Version(policy.qualification_floor)
    if parsed_version < qualification_floor:
        return CompatibilityResult(
            status='end_of_life',
            readiness='blocked',
            profile_key=contract.key,
            support_level='end_of_life',
            message=(
                f'{policy.label} {detected} is older than the KAORI '
                f'{COMPATIBILITY_LIFECYCLE_POLICY.lookback_years}-year lifecycle anchor '
                f'({COMPATIBILITY_LIFECYCLE_POLICY.anchor_year}; minimum {policy.minimum_label}). '
                'Upgrade into the supported lifecycle window before enabling this integration.'
            ),
            detected_version=detected,
            qualification_key=None,
            upstream_lifecycle='kaori_end_of_life',
        )

    qualification = next(
        (item for item in QUALIFICATIONS.get(product_key, ()) if item.matches(detected)),
        None,
    )
    required = _ordered_unique(
        (*contract.required_capabilities, *((qualification.required_capabilities) if qualification else ()))
    )
    observed = set(capabilities)
    missing = tuple(item for item in required if item not in observed)
    support_level = qualification.support_level if qualification else 'unverified'
    lifecycle = qualification.upstream_lifecycle if qualification else 'unverified'
    qualification_key = qualification.key if qualification else None

    if missing:
        return CompatibilityResult(
            status='capability_mismatch',
            readiness='blocked',
            profile_key=contract.key,
            support_level=support_level,
            message='Required API capabilities are missing: ' + ', '.join(missing),
            detected_version=detected,
            missing_capabilities=missing,
            qualification_key=qualification_key,
            upstream_lifecycle=lifecycle,
        )

    if qualification is None:
        return CompatibilityResult(
            status='unverified_version',
            readiness='degraded',
            profile_key=contract.key,
            support_level='unverified',
            message=(
                f'{policy.label} {detected} satisfies the observed {contract.key} capability contract, '
                'but this version is not yet in the KAORI qualification matrix. Treat it as unverified '
                'until qualification evidence is promoted.'
            ),
            detected_version=detected,
            qualification_key=None,
            upstream_lifecycle='unverified',
        )

    warning = qualification.support_level in {'legacy', 'deprecated', 'legacy_supported', 'extended_supported'}
    return CompatibilityResult(
        status='compatible_with_warnings' if warning else 'compatible',
        readiness='degraded' if warning else 'ready',
        profile_key=contract.key,
        support_level=qualification.support_level,
        message=qualification.notes,
        detected_version=detected,
        qualification_key=qualification.key,
        upstream_lifecycle=qualification.upstream_lifecycle,
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
    product_key = str(product or '').strip().lower()
    normalized_key = str(key).strip()
    profile = CONTRACT_PROFILES.get(normalized_key)
    if profile is not None:
        return profile if profile.supports_product(product_key) else None
    qualification = QUALIFICATIONS_BY_KEY.get(normalized_key)
    if qualification is None or qualification.product != product_key:
        return None
    return CONTRACT_PROFILES.get(qualification.contract_profile)


def get_profile_by_key(key: str | None) -> CompatibilityProfile | None:
    if not key:
        return None
    normalized_key = str(key).strip()
    profile = CONTRACT_PROFILES.get(normalized_key)
    if profile is not None:
        return profile
    qualification = QUALIFICATIONS_BY_KEY.get(normalized_key)
    return CONTRACT_PROFILES.get(qualification.contract_profile) if qualification else None


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))
