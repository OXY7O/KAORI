from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

_RELEASE_FORMAT = 'RELEASE.%Y-%m-%dT%H-%M-%SZ'

# KAORI support policy is intentionally explicit. The current MinIO provider has
# one qualified release; keeping min/max separate makes the contract range-aware
# without claiming support for releases that have not been validated yet.
SUPPORTED_RELEASE = 'RELEASE.2024-08-03T04-33-23Z'
SUPPORTED_RELEASE_MIN = SUPPORTED_RELEASE
SUPPORTED_RELEASE_MAX = SUPPORTED_RELEASE
SUPPORTED_RELEASE_RANGE_LABEL = (
    f'{SUPPORTED_RELEASE_MIN} only'
    if SUPPORTED_RELEASE_MIN == SUPPORTED_RELEASE_MAX
    else f'{SUPPORTED_RELEASE_MIN} – {SUPPORTED_RELEASE_MAX}'
)
PROFILE_KEY = 'minio-release-2024-08-03'
PROFILE_LABEL = 'MinIO RELEASE.2024-08-03'


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


MINIO_COMPATIBILITY_PROFILES = (
    MinioCompatibilityProfile(
        key=PROFILE_KEY,
        product='minio',
        label=PROFILE_LABEL,
        minimum_release=SUPPORTED_RELEASE_MIN,
        maximum_release=SUPPORTED_RELEASE_MAX,
        support_level='current',
        notes='Qualified MinIO S3 API provider contract. Observability bindings remain independently validated.',
    ),
)

# Product families are separate qualification boundaries. AStor is recognized as
# a distinct product family so it can receive its own release range later rather
# than inheriting the MinIO range by accident.
PRODUCT_PROFILE_CATALOG: dict[str, tuple[MinioCompatibilityProfile, ...]] = {
    'minio': MINIO_COMPATIBILITY_PROFILES,
    'astor': (),
}
PRODUCT_LABELS = {
    'minio': 'MinIO',
    'astor': 'AStor',
    's3_compatible': 'S3-Compatible',
}
COMPATIBILITY_PROFILE_KEYS = tuple(profile.key for profiles in PRODUCT_PROFILE_CATALOG.values() for profile in profiles)


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
        message=(f'{profile.label} is qualified by KAORI. Supported range: {profile.supported_range_label}.'),
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
