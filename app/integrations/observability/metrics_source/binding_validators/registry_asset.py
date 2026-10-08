from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.integrations.kernel.registry import get_integration
from app.integrations.observability.metrics_source.binding_profiles import BindingValidationProfile
from app.integrations.observability.metrics_source.binding_validators.contracts import BindingValidationAssessment
from app.integrations.observability.metrics_source.query_profiles.registry_harbor_audit import (
    RegistryHarborMetricsAuditor,
)
from app.models.integration import IntegrationBinding, IntegrationInstance


@dataclass(frozen=True, slots=True)
class RegistryMetricsQualification:
    provider_key: str
    asset_profile: str
    profile_label: str


_QUALIFICATIONS = {
    'harbor': RegistryMetricsQualification(
        provider_key='harbor',
        asset_profile='harbor-metrics-v1',
        profile_label='Harbor Registry Metrics v1',
    ),
}


def validate_registry_binding(
    *,
    client: Any,
    binding: IntegrationBinding,
    profile: BindingValidationProfile,
) -> BindingValidationAssessment:
    identity = db.session.get(
        IntegrationInstance,
        int(binding.asset_key) if str(binding.asset_key).isdigit() else -1,
    )
    if identity is None or identity.integration_type != 'registry':
        return BindingValidationAssessment(
            status='blocked',
            message='The Registry instance referenced by this Metrics Source binding no longer exists.',
        )

    qualification = _QUALIFICATIONS.get(identity.provider_key)
    if qualification is None:
        return BindingValidationAssessment(
            status='blocked',
            message=(
                f'No qualified Registry metrics profile is registered for provider {identity.provider_key!r}. '
                'Registry inventory remains usable without operational metrics.'
            ),
            evidence={
                'asset_profile': 'unsupported',
                'provider_key': identity.provider_key,
                'metrics_readiness': {'status': 'unsupported', 'items': []},
            },
        )

    audit = RegistryHarborMetricsAuditor(client).audit(execute_queries=True)
    versions = {str(value).lstrip('v') for value in audit.get('observed_harbor_versions') or ()}
    provider_record = get_integration('registry').require_record_for_canonical(identity.id)
    expected_version = str(getattr(provider_record, 'detected_version', '') or '').strip().lstrip('v')
    if expected_version and versions and expected_version not in versions:
        return BindingValidationAssessment(
            status='blocked',
            message=(
                'The scoped Harbor metrics identity does not match the bound Registry provider version. '
                f'Provider API reports {expected_version}; scoped metrics report {", ".join(sorted(versions))}.'
            ),
            evidence={
                'asset_profile': qualification.asset_profile,
                'provider_key': identity.provider_key,
                'metrics_readiness': audit,
                'selector_isolation': 'version_mismatch',
            },
        )

    observed = set(audit.get('observed_metrics') or ())
    identity_metrics = {'harbor_health', 'harbor_up', 'harbor_system_info'}
    matched = sorted(identity_metrics & observed)
    if len(matched) < 2:
        return BindingValidationAssessment(
            status='degraded',
            message=profile.no_match_message,
            matched_series=0,
            matched_signal=matched[0] if matched else None,
            evidence={
                'asset_profile': qualification.asset_profile,
                'provider_key': identity.provider_key,
                'metrics_readiness': audit,
                'selector_isolation': 'insufficient_identity',
            },
        )

    return BindingValidationAssessment(
        status='ready',
        message=(
            f'{profile.label} resolved {qualification.profile_label}; the selector isolates usable '
            'Registry identity metrics and provider version evidence is consistent when available.'
        ),
        matched_series=len(matched),
        matched_signal=matched[0],
        evidence={
            'asset_profile': qualification.asset_profile,
            'asset_profile_label': qualification.profile_label,
            'provider_key': identity.provider_key,
            'metrics_readiness': audit,
            'selector_isolation': 'validated',
        },
    )
