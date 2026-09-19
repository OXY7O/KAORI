from __future__ import annotations

from typing import Any

from app.integrations.registry import registry
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.metrics_source import MetricsSource
from app.models.runtime import IntegrationRuntimeObservation

CORE_OVERVIEW_PROVIDERS = frozenset({'container_orchestrator', 'metrics_source', 'alert_source', 'object_storage'})


def build_overview_stats(
    *,
    kubernetes_connections: list[KubernetesConnection],
    metrics_sources: list[MetricsSource],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> dict[str, int]:
    target_states = [
        *(
            (True, bool(connection.integration_instance.enabled), connection.readiness_status or 'validation_required')
            for connection in kubernetes_connections
        ),
        *(
            (bool(item.endpoint), bool(item.enabled), item.readiness_status or 'validation_required')
            for item in metrics_sources
        ),
        *(
            (bool(item.endpoint), bool(item.enabled), item.readiness_status or 'validation_required')
            for item in alertmanager_instances
        ),
        *((True, bool(item.enabled), item.readiness_status or 'validation_required') for item in extension_instances),
    ]
    total = len(target_states)
    configured = sum(1 for is_configured, _, _ in target_states if is_configured)
    ready = sum(
        1
        for is_configured, is_enabled, readiness in target_states
        if is_configured and is_enabled and readiness == 'ready'
    )
    readiness_review = sum(
        1
        for is_configured, is_enabled, readiness in target_states
        if is_configured and (not is_enabled or readiness != 'ready')
    )
    blocked = sum(
        1
        for is_configured, is_enabled, readiness in target_states
        if is_configured and is_enabled and readiness == 'blocked'
    )
    not_configured = max(total - configured, 0)
    return {
        'total': total,
        'configured': configured,
        'ready': ready,
        'validation_required': readiness_review,
        'readiness_review': readiness_review,
        'not_configured': not_configured,
        'attention': readiness_review + not_configured,
        'blocked': blocked,
    }


def load_extension_integration_instances() -> list[IntegrationInstance]:
    integration_types = tuple(
        module.integration_type for module in registry.all() if module.integration_type not in CORE_OVERVIEW_PROVIDERS
    )
    if not integration_types:
        return []
    return (
        IntegrationInstance.query.filter(IntegrationInstance.integration_type.in_(integration_types))
        .order_by(IntegrationInstance.integration_type.asc(), IntegrationInstance.name.asc())
        .all()
    )


def build_extension_runtime_rows(
    latest: dict[tuple[str, str], IntegrationRuntimeObservation],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module in registry.all():
        rows.extend(module.build_runtime_overview_rows(latest))
    return rows


def sort_runtime_rows(rows: list[dict[str, Any]]) -> None:
    health_order = {'unhealthy': 0, 'degraded': 1, 'not_observed': 2, 'healthy': 3}
    rows.sort(
        key=lambda row: (
            health_order.get(row['health_status'], 2),
            row['provider_label'],
            row['instance_name'].lower(),
        )
    )
