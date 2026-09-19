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
class CompatibilitySupportPosture:
    key: str
    result_status: str
    readiness: str


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
    selection_mode: str
    version_source: str
    contract_profile: str
    qualification_floor: str
    qualification_ceiling_exclusive: str
    minimum_label: str
    recommended_label: str
    qualified_version_label: str
    current_version_label: str
    upstream_supported_version_label: str
    supported_version_label: str
    anchor_release_label: str
    upper_release_label: str
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
    dict[str, CompatibilitySupportPosture],
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

    postures: dict[str, CompatibilitySupportPosture] = {}
    for index, raw in enumerate(require_list(document.get('support_postures'), 'support_postures')):
        item = require_mapping(raw, f'support_postures[{index}]')
        posture = CompatibilitySupportPosture(
            key=require_str(item, 'key', f'support_postures[{index}]'),
            result_status=require_str(item, 'result_status', f'support_postures[{index}]'),
            readiness=require_str(item, 'readiness', f'support_postures[{index}]'),
        )
        postures[posture.key] = posture

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
        product = CompatibilityProductPolicy(
            key=require_str(item, 'key', f'products[{index}]').lower(),
            label=require_str(item, 'label', f'products[{index}]'),
            icon=require_str(item, 'icon', f'products[{index}]'),
            version_scheme=require_str(item, 'version_scheme', f'products[{index}]'),
            selection_mode=require_str(item, 'selection_mode', f'products[{index}]'),
            version_source=require_str(item, 'version_source', f'products[{index}]'),
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
            current_version_label=require_str(item, 'current_version_label', f'products[{index}]'),
            upstream_supported_version_label=require_str(
                item,
                'upstream_supported_version_label',
                f'products[{index}]',
            ),
            supported_version_label=require_str(item, 'supported_version_label', f'products[{index}]'),
            anchor_release_label=require_str(item, 'anchor_release_label', f'products[{index}]'),
            upper_release_label=require_str(item, 'upper_release_label', f'products[{index}]'),
            upstream_lifecycle_label=require_str(item, 'upstream_lifecycle_label', f'products[{index}]'),
            support_label=require_str(item, 'support_label', f'products[{index}]'),
            support_tone=require_str(item, 'support_tone', f'products[{index}]'),
            capability_summary=require_str(item, 'capability_summary', f'products[{index}]'),
            validation_basis=require_str(item, 'validation_basis', f'products[{index}]'),
        )
        products[product.key] = product

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

    return lifecycle, postures, contracts, products, {product: tuple(items) for product, items in grouped.items()}


(
    COMPATIBILITY_LIFECYCLE_POLICY,
    SUPPORT_POSTURES,
    CONTRACT_PROFILES,
    PRODUCT_POLICIES,
    QUALIFICATIONS,
) = _load_compatibility_contract()

# Backward-compatible import name: these are version qualification rows, not runtime contract profiles.
PROFILES = QUALIFICATIONS
QUALIFICATIONS_BY_KEY = {
    qualification.key: qualification for qualifications in QUALIFICATIONS.values() for qualification in qualifications
}


def resolve_qualification(product: str, version: str | None) -> CompatibilityQualification | None:
    product_key = str(product or '').strip().lower()
    if product_key not in PRODUCT_POLICIES or not version:
        return None
    normalized = normalize_runtime_version(version)
    try:
        Version(normalized)
    except InvalidVersion:
        return None
    return next(
        (item for item in QUALIFICATIONS.get(product_key, ()) if item.matches(normalized)),
        None,
    )


def resolve_contract_profile(product: str, version: str | None) -> CompatibilityProfile | None:
    product_key = str(product or '').strip().lower()
    policy = PRODUCT_POLICIES.get(product_key)
    if policy is None:
        return None
    qualification = resolve_qualification(product_key, version)
    profile_key = qualification.contract_profile if qualification else policy.contract_profile
    profile = CONTRACT_PROFILES.get(profile_key)
    if profile is None or not profile.supports_product(product_key):
        return None
    return profile


def compatibility_selection_policy(product: str) -> dict[str, str]:
    policy = PRODUCT_POLICIES[str(product or '').strip().lower()]
    return {
        'selection_mode': policy.selection_mode,
        'version_source': policy.version_source,
        'default_contract_profile': policy.contract_profile,
        'qualification_floor': policy.qualification_floor,
        'qualification_ceiling_exclusive': policy.qualification_ceiling_exclusive,
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

    raw = (version or '').strip() or None
    detected = normalize_runtime_version(raw) if raw else None
    if not detected or detected.lower() == 'unknown':
        return CompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=policy.contract_profile,
            support_level='unknown',
            message=(
                f'{policy.label} responded, but KAORI could not determine a usable runtime version. '
                'Automatic version identity is required before qualification can be evaluated.'
            ),
            detected_version=detected,
        )

    try:
        parsed_version = Version(detected)
    except InvalidVersion:
        return CompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=policy.contract_profile,
            support_level='unknown',
            message=f'{policy.label} returned an unparseable runtime version: {detected}.',
            detected_version=detected,
        )

    qualification = resolve_qualification(product_key, detected)
    qualification_floor = Version(policy.qualification_floor)
    if parsed_version < qualification_floor:
        posture = SUPPORT_POSTURES[COMPATIBILITY_LIFECYCLE_POLICY.pre_window_posture]
        return CompatibilityResult(
            status=posture.result_status,
            readiness=posture.readiness,
            profile_key=policy.contract_profile,
            support_level=posture.key,
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

    contract = resolve_contract_profile(product_key, detected)
    if contract is None:
        return CompatibilityResult(
            status='contract_unavailable',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=f'{policy.label} {detected} resolved to an unavailable compatibility contract.',
            detected_version=detected,
            qualification_key=qualification.key if qualification else None,
        )

    required = _ordered_unique(
        (*contract.required_capabilities, *((qualification.required_capabilities) if qualification else ()))
    )
    observed = set(capabilities)
    missing = tuple(item for item in required if item not in observed)
    support_level = qualification.support_level if qualification else COMPATIBILITY_LIFECYCLE_POLICY.future_posture
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
        posture = SUPPORT_POSTURES[COMPATIBILITY_LIFECYCLE_POLICY.future_posture]
        return CompatibilityResult(
            status=posture.result_status,
            readiness=posture.readiness,
            profile_key=contract.key,
            support_level=posture.key,
            message=(
                f'{policy.label} {detected} satisfies the observed {contract.key} capability contract, '
                'but no definition band currently qualifies this version. Treat it as unverified until '
                'annual qualification evidence is promoted.'
            ),
            detected_version=detected,
            qualification_key=None,
            upstream_lifecycle='unverified',
        )

    posture = SUPPORT_POSTURES[qualification.support_level]
    return CompatibilityResult(
        status=posture.result_status,
        readiness=posture.readiness,
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


def kubernetes_lifecycle(version: str | None) -> str:
    policy = PRODUCT_POLICIES['kubernetes']
    normalized = normalize_runtime_version(version or '')
    try:
        parsed = Version(normalized)
    except InvalidVersion:
        return 'unknown'
    if parsed < Version(policy.qualification_floor):
        return 'end_of_life'
    qualification = resolve_qualification('kubernetes', normalized)
    if qualification is None:
        return 'unknown'
    if qualification.support_level == 'current':
        return 'current'
    if qualification.support_level == 'extended_supported':
        return 'extended'
    return qualification.support_level


def kubernetes_lifecycle_policy(version: str | None) -> dict[str, str]:
    """Return the definition-driven KAORI Kubernetes lifecycle contract."""
    policy = PRODUCT_POLICIES['kubernetes']
    detected = normalize_runtime_version(version or '') or 'unknown'
    return {
        'detected_version': f'v{detected}' if detected != 'unknown' else 'Unknown',
        'lifecycle_status': kubernetes_lifecycle(detected),
        'current_version_band': policy.current_version_label,
        'upstream_supported_version_band': policy.upstream_supported_version_label,
        'supported_version_band': policy.supported_version_label,
        'supported_constraint': f'>={policy.qualification_floor},<{policy.qualification_ceiling_exclusive}',
        'policy_label': 'KAORI Kubernetes lifecycle policy',
        'policy_key': COMPATIBILITY_LIFECYCLE_POLICY.key,
        'policy_version': f'v{COMPATIBILITY_LIFECYCLE_POLICY.version}',
        'policy_year': str(COMPATIBILITY_LIFECYCLE_POLICY.policy_year),
        'anchor_year': str(COMPATIBILITY_LIFECYCLE_POLICY.anchor_year),
        'lookback_years': str(COMPATIBILITY_LIFECYCLE_POLICY.lookback_years),
        'window_label': COMPATIBILITY_LIFECYCLE_POLICY.window_label,
        'snapshot_date': COMPATIBILITY_LIFECYCLE_POLICY.snapshot_date,
        'selection_mode': policy.selection_mode,
        'version_source': policy.version_source,
    }


def _constraint_bound(constraint: str, prefix: str) -> Version:
    for token in (item.strip() for item in constraint.split(',')):
        if token.startswith(prefix):
            return Version(token[len(prefix) :])
    raise ValueError(f'Constraint {constraint!r} has no {prefix!r} bound.')


_KUBERNETES_POLICY = PRODUCT_POLICIES['kubernetes']
_KUBERNETES_CURRENT = next(
    item for item in QUALIFICATIONS['kubernetes'] if item.support_level == 'current'
)
KUBERNETES_SUPPORTED_VERSION_CONSTRAINT = (
    f'>={_KUBERNETES_POLICY.qualification_floor},<{_KUBERNETES_POLICY.qualification_ceiling_exclusive}'
)
KUBERNETES_EXTENDED_MIN_VERSION = Version(_KUBERNETES_POLICY.qualification_floor)
KUBERNETES_LEGACY_MIN_VERSION = KUBERNETES_EXTENDED_MIN_VERSION
KUBERNETES_CURRENT_MIN_VERSION = _constraint_bound(_KUBERNETES_CURRENT.version_constraint, '>=')
KUBERNETES_CURRENT_MAX_VERSION_EXCLUSIVE = _constraint_bound(_KUBERNETES_CURRENT.version_constraint, '<')
KUBERNETES_CURRENT_VERSION_LABEL = _KUBERNETES_POLICY.current_version_label
KUBERNETES_UPSTREAM_SUPPORTED_VERSION_LABEL = _KUBERNETES_POLICY.upstream_supported_version_label
KUBERNETES_SUPPORTED_VERSION_LABEL = _KUBERNETES_POLICY.supported_version_label


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
