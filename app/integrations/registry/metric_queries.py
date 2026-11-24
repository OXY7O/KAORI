"""Provider-qualified semantic Registry queries using the existing Metrics Source registry.

Provider identity is resolved before a query can reach an external Metrics Source.
Unqualified provider products must not accidentally execute Harbor PromQL.
"""

from __future__ import annotations

from collections.abc import Callable

from app.integrations.observability.metrics_source.query_profiles.registry import QueryReference
from app.integrations.observability.metrics_source.query_profiles.registry_harbor_v1 import (
    get_registry_query_expression as harbor_registry_query,
)
from app.models.integration import IntegrationInstance

# Provider-specific expressions stay in versioned Metrics Source query profiles.
# Add a provider only after source identity, labels, capabilities and UAT qualify.
_QUALIFIED_QUERY_PROFILES: dict[str, Callable[[str], QueryReference]] = {
    'harbor': harbor_registry_query,
}


def qualified_registry_metric_query(identity: IntegrationInstance, key: str) -> QueryReference:
    """Resolve one semantic Registry metric only for an explicitly qualified provider."""
    if identity.integration_type != 'registry':
        raise LookupError('Registry metric profile requires a Registry integration instance.')
    provider_key = str(identity.provider_key or '').strip().lower()
    query_builder = _QUALIFIED_QUERY_PROFILES.get(provider_key)
    if query_builder is None:
        raise LookupError('No qualified operational metrics query profile is registered for this Registry provider.')
    return query_builder(key)
