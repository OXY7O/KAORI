from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import case

from app.models.integration import IntegrationBinding, IntegrationInstance

_ROLE_ORDER = {'primary': 0, 'secondary': 1, 'fallback': 2}
_BLOCKED = {'blocked', 'unavailable', 'disabled', 'incompatible'}


@dataclass(frozen=True, slots=True)
class IntegrationCandidate:
    instance: IntegrationInstance
    binding: IntegrationBinding
    eligible: bool
    missing_capabilities: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class IntegrationResolution:
    provider_type: str
    asset_type: str
    asset_key: str
    required_capabilities: tuple[str, ...]
    candidates: tuple[IntegrationCandidate, ...]

    @property
    def selected(self) -> IntegrationCandidate | None:
        return next((item for item in self.candidates if item.eligible), None)


def resolve_integration(
    *,
    provider_type: str,
    asset_type: str,
    asset_key: str,
    required_capabilities: tuple[str, ...] = (),
) -> IntegrationResolution:
    rows = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.provider_type == provider_type,
            IntegrationInstance.enabled.is_(True),
            IntegrationBinding.asset_type == asset_type,
            IntegrationBinding.asset_key == str(asset_key),
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(
            case((IntegrationBinding.binding_role == 'primary', 0),
                 (IntegrationBinding.binding_role == 'secondary', 1), else_=2),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )
    candidates: list[IntegrationCandidate] = []
    for binding in rows:
        instance = binding.instance
        scope = set(binding.capability_scope or ())
        missing = tuple(sorted(set(required_capabilities) - scope)) if scope else ()
        readiness = (instance.readiness_status or '').lower()
        eligible = bool(instance.enabled and binding.enabled and readiness not in _BLOCKED and not missing)
        if missing:
            reason = f'Missing binding capabilities: {", ".join(missing)}.'
        elif readiness in _BLOCKED:
            reason = f'Runtime readiness {readiness or "unknown"} blocks selection.'
        elif eligible:
            reason = 'Runtime satisfies asset mapping and capability requirements.'
        else:
            reason = 'Runtime is not eligible for selection.'
        candidates.append(IntegrationCandidate(instance, binding, eligible, missing, reason))
    candidates.sort(key=lambda item: (
        0 if item.eligible else 1,
        _ROLE_ORDER.get(item.binding.binding_role, 9),
        item.binding.priority,
        item.binding.id,
    ))
    return IntegrationResolution(provider_type, asset_type, str(asset_key), required_capabilities, tuple(candidates))


def provider_record(instance: IntegrationInstance) -> Any | None:
    """Resolve the provider-specific connection record without coupling consumers to its table."""
    if instance.provider_type == 'prometheus':
        from app.models.prometheus import PrometheusInstance
        return PrometheusInstance.query.filter_by(integration_instance_id=instance.id).first()
    if instance.provider_type == 'alertmanager':
        from app.models.alertmanager import AlertmanagerInstance
        return AlertmanagerInstance.query.filter_by(integration_instance_id=instance.id).first()
    if instance.provider_type == 'kubernetes':
        from app.models.kubernetes import KubernetesConnection
        return KubernetesConnection.query.filter_by(integration_instance_id=instance.id).first()
    return None
