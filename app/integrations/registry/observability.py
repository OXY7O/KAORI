from __future__ import annotations

from typing import TypedDict

from sqlalchemy.orm import joinedload

from app.integrations.observability.metrics_source.application.resolver import (
    _evaluate_binding,
    resolve_metrics_sources,
)
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.metrics_source import MetricsSource


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


def registry_metrics_ready_provider_ids(identities: list[IntegrationInstance]) -> set[int]:
    """Batch fleet readiness using the same canonical resolver eligibility evaluator.

    Avoid an asset-scoped Metrics Source resolver (and its provider-record reads)
    for every provider on an aggregate dashboard view.
    """
    ids = {str(identity.id) for identity in identities}
    if not ids:
        return set()
    bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .options(joinedload(IntegrationBinding.instance))
        .filter(
            IntegrationInstance.integration_type == 'metrics_source',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationBinding.asset_type == 'registry_instance',
            IntegrationBinding.asset_key.in_(ids),
            IntegrationBinding.enabled.is_(True),
        )
        .all()
    )
    if not bindings:
        return set()
    source_ids = {binding.integration_instance_id for binding in bindings}
    sources = {
        source.integration_instance_id: source
        for source in MetricsSource.query.filter(
            MetricsSource.integration_instance_id.in_(source_ids)
        ).all()
    }
    ready: set[int] = set()
    for binding in bindings:
        source = sources.get(binding.integration_instance_id)
        if source is None:
            continue
        candidate = _evaluate_binding(
            binding,
            source,
            missing_binding_capabilities=(),
            required_technical_capabilities=('instant_query',),
            query_horizon='balanced',
        )
        if candidate.eligible:
            ready.add(int(binding.asset_key))
    return ready
