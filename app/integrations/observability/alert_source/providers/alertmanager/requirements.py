from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.integrations.observability.alert_source.providers.alertmanager.capabilities import CAPABILITY_BY_KEY


@dataclass(frozen=True, slots=True)
class ModuleRequirement:
    key: str
    label: str
    description: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    operator_guidance: str = ''


MODULE_REQUIREMENTS: tuple[ModuleRequirement, ...] = (
    ModuleRequirement(
        'provider_identity',
        'Provider Identity',
        'Reads Alertmanager status and build information for product/version compatibility.',
        ('status_v2',),
        operator_guidance='Restore /api/v2/status access before relying on this Alertmanager provider.',
    ),
    ModuleRequirement(
        'alerts_api',
        'Alerts API',
        'Confirms the provider can serve the active-alert API independently from any consumer selector.',
        ('alerts_v2',),
        operator_guidance='Restore /api/v2/alerts access. Consumer-specific alert identity is validated after binding.',
    ),
    ModuleRequirement(
        'silences_api',
        'Silences API',
        'Confirms the provider can serve silence inventory independently from any managed asset.',
        ('silences_v2',),
        operator_guidance='Restore /api/v2/silences access before enabling silence-aware consumers.',
    ),
)


def evaluate_module_readiness(capabilities: Iterable[str]) -> list[dict[str, object]]:
    observed = set(capabilities)
    rows: list[dict[str, object]] = []
    for requirement in MODULE_REQUIREMENTS:
        missing_required = [key for key in requirement.required_capabilities if key not in observed]
        missing_optional = [key for key in requirement.optional_capabilities if key not in observed]
        if missing_required:
            status = 'unavailable'
        elif missing_optional:
            status = 'degraded'
        else:
            status = 'ready'
        rows.append(
            {
                'key': requirement.key,
                'label': requirement.label,
                'description': requirement.description,
                'status': status,
                'required_capabilities': list(requirement.required_capabilities),
                'optional_capabilities': list(requirement.optional_capabilities),
                'required_capability_labels': [
                    CAPABILITY_BY_KEY[key].label for key in requirement.required_capabilities
                ],
                'optional_capability_labels': [
                    CAPABILITY_BY_KEY[key].label for key in requirement.optional_capabilities
                ],
                'missing_required': missing_required,
                'missing_required_labels': [CAPABILITY_BY_KEY[key].label for key in missing_required],
                'missing_optional': missing_optional,
                'missing_optional_labels': [CAPABILITY_BY_KEY[key].label for key in missing_optional],
                'operator_guidance': requirement.operator_guidance,
            }
        )
    return rows
