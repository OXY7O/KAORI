from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_RELEASE = 'RELEASE.2024-08-03T04-33-23Z'
PROFILE_KEY = 'minio-release-2024-08-03'
PROFILE_LABEL = 'MinIO RELEASE.2024-08-03'


@dataclass(frozen=True, slots=True)
class MinioCompatibilityResult:
    status: str
    readiness: str
    profile_key: str | None
    support_level: str
    message: str
    declared_release: str | None


def evaluate_minio_release(value: str | None) -> MinioCompatibilityResult:
    release = str(value or '').strip() or None
    if release is None:
        return MinioCompatibilityResult(
            status='version_unknown',
            readiness='blocked',
            profile_key=None,
            support_level='unknown',
            message='Declare the MinIO server release before KAORI can activate this compatibility contract.',
            declared_release=None,
        )
    if release != SUPPORTED_RELEASE:
        return MinioCompatibilityResult(
            status='unsupported_version',
            readiness='blocked',
            profile_key=None,
            support_level='blocked',
            message=(
                f'MinIO {release} is not covered by the current KAORI MinIO profile. '
                f'This phase supports {SUPPORTED_RELEASE}.'
            ),
            declared_release=release,
        )
    return MinioCompatibilityResult(
        status='compatible',
        readiness='ready',
        profile_key=PROFILE_KEY,
        support_level='current',
        message=(
            'The declared MinIO release matches the KAORI MinIO 2024 object-storage API and Prometheus v2 '
            'metrics contract.'
        ),
        declared_release=release,
    )
