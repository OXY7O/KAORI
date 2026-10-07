from __future__ import annotations

from typing import TypedDict

from app.integrations.observability.metrics_source.application.resolver import resolve_metrics_sources
from app.models.integration import IntegrationBinding, IntegrationInstance


class RegistryMetricsReadiness(TypedDict):
    status: str
    label: str
    tone: str
    binding_count: int
    validated_binding_count: int
    selected_source: str | None
    detail: str


def registry_metrics_readiness(identity: IntegrationInstance) -> RegistryMetricsReadiness:
    """Return DB-backed Metrics Source readiness without executing a provider query."""

    bindings = (
        IntegrationBinding.query.join(
            IntegrationInstance,
            IntegrationBinding.integration_instance_id == IntegrationInstance.id,
        )
        .filter(
            IntegrationInstance.integration_type == 'metrics_source',
            IntegrationBinding.asset_type == 'registry_instance',
            IntegrationBinding.asset_key == str(identity.id),
            IntegrationBinding.enabled.is_(True),
        )
        .all()
    )
    validated = [binding for binding in bindings if binding.validation_status == 'ready']
    resolution = resolve_metrics_sources(
        scope_type='registry_instance',
        scope_key=str(identity.id),
        required_technical_capabilities=('instant_query',),
    )
    selected = resolution.selected

    if selected is None:
        return {
            'status': 'unavailable' if bindings else 'not_bound',
            'label': 'Unavailable' if bindings else 'Not Bound',
            'tone': 'warning' if bindings else 'unknown',
            'binding_count': len(bindings),
            'validated_binding_count': len(validated),
            'selected_source': None,
            'detail': '; '.join(candidate.decision_reason for candidate in resolution.candidates),
        }
    return {
        'status': 'ready',
        'label': 'Ready',
        'tone': 'normal',
        'binding_count': len(bindings),
        'validated_binding_count': len(validated),
        'selected_source': selected.instance.name,
        'detail': selected.decision_reason,
    }
