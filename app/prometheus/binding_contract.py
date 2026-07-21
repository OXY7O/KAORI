from __future__ import annotations

from app.models.integration import IntegrationBinding
from app.prometheus.repository import KUBERNETES_CLUSTER_SCOPE

PROMETHEUS_BINDING_CAPABILITIES: tuple[str, ...] = (
    'metrics',
    'capacity',
    'utilization',
    'storage',
    'workload',
    'forecast',
    'top_consumers',
    'alert_metrics',
)


def effective_prometheus_binding_capabilities(binding: IntegrationBinding) -> tuple[str, ...]:
    """Return the effective capability contract for a Kubernetes binding.

    Early shared-source bindings were created before KAORI exposed a configurable
    binding capability contract. Those rows can contain an empty, partial, or
    provider-neutral scope even though the UI never offered the operator a way to
    narrow Prometheus consumer access. Managed-cluster bindings therefore inherit
    the current complete default contract while preserving any future/custom values.
    """
    current = tuple(
        str(item).strip()
        for item in (binding.capability_scope or ())
        if str(item).strip()
    )
    if binding.asset_type != KUBERNETES_CLUSTER_SCOPE:
        return tuple(dict.fromkeys(current))
    return tuple(dict.fromkeys((*PROMETHEUS_BINDING_CAPABILITIES, *current)))


def normalize_prometheus_binding_capabilities(binding: IntegrationBinding) -> bool:
    """Persist the effective default capability contract for legacy bindings."""
    effective = list(effective_prometheus_binding_capabilities(binding))
    current = [
        str(item).strip()
        for item in (binding.capability_scope or ())
        if str(item).strip()
    ]
    if current == effective:
        return False
    binding.capability_scope = effective
    return True
