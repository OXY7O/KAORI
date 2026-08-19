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
    minimum_release: str
    maximum_release: str
    support_level: str
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


def _load_compatibility_contract() -> tuple[
    dict[str, tuple[MinioCompatibilityProfile, ...]],
    dict[str, str],
]:
    document = integration_provider_document('object_storage')
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
                    notes=require_str(
                        profile,
                        'notes',
                        f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]',
                    ),
                )
            )
        catalog[product_key] = tuple(profiles)
    return catalog, labels


PRODUCT_PROFILE_CATALOG, PRODUCT_LABELS = _load_compatibility_contract()
MINIO_COMPATIBILITY_PROFILES = PRODUCT_PROFILE_CATALOG.get('minio', ())
COMPATIBILITY_PROFILE_KEYS = tuple(profile.key for profiles in PRODUCT_PROFILE_CATALOG.values() for profile in profiles)

_PRIMARY_MINIO_PROFILE = MINIO_COMPATIBILITY_PROFILES[0] if MINIO_COMPATIBILITY_PROFILES else None
SUPPORTED_RELEASE = _PRIMARY_MINIO_PROFILE.minimum_release if _PRIMARY_MINIO_PROFILE else ''
SUPPORTED_RELEASE_MIN = _PRIMARY_MINIO_PROFILE.minimum_release if _PRIMARY_MINIO_PROFILE else ''
SUPPORTED_RELEASE_MAX = _PRIMARY_MINIO_PROFILE.maximum_release if _PRIMARY_MINIO_PROFILE else ''
SUPPORTED_RELEASE_RANGE_LABEL = (
    _PRIMARY_MINIO_PROFILE.supported_range_label if _PRIMARY_MINIO_PROFILE else 'Qualification Required'
)
PROFILE_KEY = _PRIMARY_MINIO_PROFILE.key if _PRIMARY_MINIO_PROFILE else 'Qualification Required'
PROFILE_LABEL = _PRIMARY_MINIO_PROFILE.label if _PRIMARY_MINIO_PROFILE else 'Qualification Required'


def compatibility_policy_view(product: str | None, release: str | None = None) -> dict[str, str]:
    product_key = _normalize_product(product)
    profiles = PRODUCT_PROFILE_CATALOG.get(product_key, ())
    profile = next((item for item in profiles if release and item.matches(release)), None)
    if profile is None and profiles:
        profile = profiles[0]
    return {
        'product_key': product_key,
        'product_label': PRODUCT_LABELS.get(product_key, product_key.replace('_', ' ').title()),
        'profile_key': profile.key if profile else 'Qualification Required',
        'profile_label': profile.label if profile else 'Qualification Required',
        'supported_range': profile.supported_range_label if profile else 'Product-Specific Qualification Required',
        'support_level': profile.support_level if profile else 'unqualified',
    }


def evaluate_minio_release(value: str | None, *, product: str | None = 'minio') -> MinioCompatibilityResult:
    release = str(value or '').strip() or None
    product_key = _normalize_product(product)
    policy = compatibility_policy_view(product_key, release)
    if release is None:
        return MinioCompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=None,
            support_level='unknown',
            message='Declare the object-storage provider release before KAORI can activate a compatibility profile.',
            declared_release=None,
            product=product_key,
            supported_range=policy['supported_range'],
        )

    profiles = PRODUCT_PROFILE_CATALOG.get(product_key)
    if profiles is None:
        return MinioCompatibilityResult(
            status='product_unsupported',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=(
                f'{policy["product_label"]} is not mapped to a KAORI object-storage compatibility profile. '
                'Keep this product family isolated until a release range is qualified.'
            ),
            declared_release=release,
            product=product_key,
            supported_range=policy['supported_range'],
        )
    if not profiles:
        return MinioCompatibilityResult(
            status='product_unqualified',
            readiness='blocked',
            profile_key=None,
            support_level='unqualified',
            message=(
                f'{policy["product_label"]} was detected, but KAORI has no qualified release range for this product family yet.'
            ),
            declared_release=release,
            product=product_key,
            supported_range=policy['supported_range'],
        )

    profile = next((item for item in profiles if item.matches(release)), None)
    if profile is None:
        supported = '; '.join(item.supported_range_label for item in profiles)
        return MinioCompatibilityResult(
            status='unsupported_version',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=(
                f'{policy["product_label"]} {release} is outside the qualified KAORI release range. '
                f'Supported range: {supported}.'
            ),
            declared_release=release,
            product=product_key,
            supported_range=supported,
        )

    return MinioCompatibilityResult(
        status='compatible',
        readiness='ready',
        profile_key=profile.key,
        support_level=profile.support_level,
        message=(f'{profile.label} is qualified by KAORI.'),
        declared_release=release,
        product=product_key,
        supported_range=profile.supported_range_label,
    )


def _parse_release(value: str) -> datetime | None:
    try:
        return datetime.strptime(str(value or '').strip(), _RELEASE_FORMAT)
    except ValueError:
        return None


def _normalize_product(value: str | None) -> str:
    return str(value or 'minio').strip().lower().replace('-', '_') or 'minio'
