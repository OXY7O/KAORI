from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_list, require_mapping, require_str

_RELEASE_FORMAT = 'RELEASE.%Y-%m-%dT%H-%M-%SZ'


@dataclass(frozen=True, slots=True)
class MinioCompatibilityProfile:
    key: str
    product: str
    label: str
    contract_profile: str
    minimum_release: str
    maximum_release: str
    support_level: str
    upstream_lifecycle: str
    notes: str

    @property
    def supported_range_label(self) -> str:
        if self.minimum_release == self.maximum_release:
            return f'{self.minimum_release} only'
        return f'{self.minimum_release} – {self.maximum_release}'

    def matches(self, release: str) -> bool:
        parsed = _parse_release(release)
        minimum = _parse_release(self.minimum_release)
        maximum = _parse_release(self.maximum_release)
        return parsed is not None and minimum is not None and maximum is not None and minimum <= parsed <= maximum


@dataclass(frozen=True, slots=True)
class MinioCompatibilityResult:
    status: str
    readiness: str
    profile_key: str | None
    support_level: str
    message: str
    declared_release: str | None
    product: str
    supported_range: str
    qualification_key: str | None = None
    upstream_lifecycle: str = 'unknown'


def _load_compatibility_contract() -> tuple[
    str,
    dict[str, tuple[MinioCompatibilityProfile, ...]],
    dict[str, str],
]:
    document = integration_provider_document('object_storage')
    contract_profile = require_str(document, 'capability_profile', 'object_storage')
    catalog: dict[str, tuple[MinioCompatibilityProfile, ...]] = {}
    labels: dict[str, str] = {}
    for product_index, raw_product in enumerate(require_list(document.get('products'), 'object_storage.products')):
        product = require_mapping(raw_product, f'object_storage.products[{product_index}]')
        product_key = require_str(product, 'key', f'object_storage.products[{product_index}]')
        labels[product_key] = require_str(product, 'label', f'object_storage.products[{product_index}]')
        profiles: list[MinioCompatibilityProfile] = []
        for profile_index, raw_profile in enumerate(
            require_list(
                product.get('compatibility_profiles'),
                f'object_storage.products[{product_index}].compatibility_profiles',
            )
        ):
            profile = require_mapping(
                raw_profile,
                f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
            )
            profiles.append(
                MinioCompatibilityProfile(
                    key=require_str(
                        profile,
                        'key',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    product=require_str(
                        profile,
                        'product',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    label=require_str(
                        profile,
                        'label',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    contract_profile=require_str(
                        profile,
                        'contract_profile',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    minimum_release=require_str(
                        profile,
                        'minimum_release',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    maximum_release=require_str(
                        profile,
                        'maximum_release',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    support_level=require_str(
                        profile,
                        'support_level',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    upstream_lifecycle=require_str(
                        profile,
                        'upstream_lifecycle',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                    notes=require_str(
                        profile,
                        'notes',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                )
            )
        catalog[product_key] = tuple(profiles)
    return contract_profile, catalog, labels


CONTRACT_PROFILE, PRODUCT_PROFILE_CATALOG, PRODUCT_LABELS = _load_compatibility_contract()
MINIO_COMPATIBILITY_PROFILES = PRODUCT_PROFILE_CATALOG.get('minio', ())
COMPATIBILITY_PROFILE_KEYS = tuple(profile.key for profiles in PRODUCT_PROFILE_CATALOG.values() for profile in profiles)

_PRIMARY_MINIO_PROFILE = MINIO_COMPATIBILITY_PROFILES[0] if MINIO_COMPATIBILITY_PROFILES else None
SUPPORTED_RELEASE = _PRIMARY_MINIO_PROFILE.minimum_release if _PRIMARY_MINIO_PROFILE else ''
SUPPORTED_RELEASE_MIN = _PRIMARY_MINIO_PROFILE.minimum_release if _PRIMARY_MINIO_PROFILE else ''
SUPPORTED_RELEASE_MAX = _PRIMARY_MINIO_PROFILE.maximum_release if _PRIMARY_MINIO_PROFILE else ''
SUPPORTED_RELEASE_RANGE_LABEL = (
    _PRIMARY_MINIO_PROFILE.supported_range_label if _PRIMARY_MINIO_PROFILE else 'Qualification Required'
)
PROFILE_KEY = CONTRACT_PROFILE
QUALIFICATION_KEY = _PRIMARY_MINIO_PROFILE.key if _PRIMARY_MINIO_PROFILE else ''
PROFILE_LABEL = _PRIMARY_MINIO_PROFILE.label if _PRIMARY_MINIO_PROFILE else 'Qualification Required'


def compatibility_policy_view(product: str | None, release: str | None = None) -> dict[str, str]:
    product_key = _normalize_product(product)
    profiles = PRODUCT_PROFILE_CATALOG.get(product_key, ())
    profile = next((item for item in profiles if release and item.matches(release)), None)
    supported_range = (
        '; '.join(item.supported_range_label for item in profiles) or 'Product-Specific Qualification Required'
    )
    return {
        'product_key': product_key,
        'product_label': PRODUCT_LABELS.get(product_key, product_key.replace('_', ' ').title()),
        'profile_key': CONTRACT_PROFILE if product_key in PRODUCT_PROFILE_CATALOG else 'Qualification Required',
        'profile_label': CONTRACT_PROFILE if product_key in PRODUCT_PROFILE_CATALOG else 'Qualification Required',
        'contract_profile': CONTRACT_PROFILE,
        'qualification_key': profile.key if profile else 'Unverified Version',
        'supported_range': supported_range,
        'support_level': profile.support_level if profile else 'unverified',
        'upstream_lifecycle': profile.upstream_lifecycle if profile else 'unverified',
    }


def evaluate_minio_release(value: str | None, *, product: str | None = 'minio') -> MinioCompatibilityResult:
    release = str(value or '').strip() or None
    product_key = _normalize_product(product)
    profiles = PRODUCT_PROFILE_CATALOG.get(product_key)

    if profiles is None:
        return MinioCompatibilityResult(
            status='product_unsupported',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=(
                f'{PRODUCT_LABELS.get(product_key, product_key.replace("_", " ").title())} is not registered '
                'in the KAORI object-storage provider catalog.'
            ),
            declared_release=release,
            product=product_key,
            supported_range='Product-Specific Qualification Required',
        )

    supported_range = (
        '; '.join(item.supported_range_label for item in profiles) or 'Product-Specific Qualification Required'
    )

    if not profiles:
        return MinioCompatibilityResult(
            status='product_unqualified',
            readiness='degraded',
            profile_key=CONTRACT_PROFILE,
            support_level='unverified',
            message=(
                f'{PRODUCT_LABELS.get(product_key, product_key.replace("_", " ").title())} can satisfy the general '
                f'{CONTRACT_PROFILE} capability contract, but no product release range is qualified yet.'
            ),
            declared_release=release,
            product=product_key,
            supported_range=supported_range,
        )

    if release is None:
        return MinioCompatibilityResult(
            status='version_unknown',
            readiness='degraded',
            profile_key=CONTRACT_PROFILE,
            support_level='unverified',
            message=(
                f'The S3 capability contract can be validated independently, but the {PRODUCT_LABELS[product_key]} '
                'release is not declared. Keep version qualification unverified.'
            ),
            declared_release=None,
            product=product_key,
            supported_range=supported_range,
        )

    profile = next((item for item in profiles if item.matches(release)), None)
    if profile is None:
        parsed_release = _parse_release(release)
        parsed_minimum_releases = [
            parsed_minimum for item in profiles if (parsed_minimum := _parse_release(item.minimum_release)) is not None
        ]
        minimum_release = min(parsed_minimum_releases, default=None)
        if parsed_release is not None and minimum_release is not None and parsed_release < minimum_release:
            return MinioCompatibilityResult(
                status='end_of_life',
                readiness='blocked',
                profile_key=CONTRACT_PROFILE,
                support_level='end_of_life',
                message=(
                    f'{PRODUCT_LABELS[product_key]} {release} is older than the KAORI lifecycle floor '
                    f'({profiles[0].minimum_release}). Upgrade into the current five-year qualification window.'
                ),
                declared_release=release,
                product=product_key,
                supported_range=supported_range,
                upstream_lifecycle='kaori_end_of_life',
            )
        return MinioCompatibilityResult(
            status='unverified_version',
            readiness='degraded',
            profile_key=CONTRACT_PROFILE,
            support_level='unverified',
            message=(
                f'{PRODUCT_LABELS[product_key]} {release} is newer than or outside the currently qualified '
                f'lifecycle window. Core S3 readiness may proceed through {CONTRACT_PROFILE}; treat product-version '
                'qualification as unverified until annual policy evidence is promoted.'
            ),
            declared_release=release,
            product=product_key,
            supported_range=supported_range,
        )

    return MinioCompatibilityResult(
        status='compatible',
        readiness='ready',
        profile_key=profile.contract_profile,
        support_level=profile.support_level,
        message=profile.notes,
        declared_release=release,
        product=product_key,
        supported_range=profile.supported_range_label,
        qualification_key=profile.key,
        upstream_lifecycle=profile.upstream_lifecycle,
    )


def _parse_release(value: str) -> datetime | None:
    try:
        return datetime.strptime(str(value or '').strip(), _RELEASE_FORMAT)
    except ValueError:
        return None


def _normalize_product(value: str | None) -> str:
    return str(value or 'minio').strip().lower().replace('-', '_') or 'minio'
