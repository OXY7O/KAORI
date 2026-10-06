from __future__ import annotations

from typing import Any

from app.integrations.kernel.registry import registry
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.metrics_source import MetricsSource
from app.models.runtime import IntegrationRuntimeObservation

SPECIALIZED_OVERVIEW_TYPES = frozenset({'container_orchestrator', 'metrics_source', 'alert_source'})


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



def portfolio_counts(states: list[tuple[bool, bool, str | None]]) -> dict[str, int]:
    counts = {
        'configured': 0,
        'ready': 0,
        'degraded': 0,
        'blocked': 0,
        'validation_required': 0,
        'disabled': 0,
        'not_configured': 0,
        'total': 0,
        'attention': 0,
    }
    for is_configured, is_enabled, readiness in states:
        counts['total'] += 1
        if not is_configured:
            counts['not_configured'] += 1
            continue
        counts['configured'] += 1
        if not is_enabled:
            counts['disabled'] += 1
            continue
        state = str(readiness or 'validation_required').strip().lower()
        if state == 'ready':
            counts['ready'] += 1
        elif state == 'degraded':
            counts['degraded'] += 1
        elif state in {'blocked', 'unavailable', 'failed', 'incompatible'}:
            counts['blocked'] += 1
        else:
            counts['validation_required'] += 1
    counts['attention'] = max(counts['total'] - counts['ready'], 0)
    return counts


def portfolio_posture(counts: dict[str, int]) -> tuple[str, str]:
    total = int(counts.get('total') or 0)
    configured = int(counts.get('configured') or 0)
    ready = int(counts.get('ready') or 0)
    if total <= 0 or configured <= 0:
        return 'not_configured', 'Not Configured'
    if ready == total:
        return 'ready', 'Ready'
    if total == 1:
        for key, label in (
            ('degraded', 'Degraded'),
            ('blocked', 'Blocked'),
            ('validation_required', 'Validation Required'),
            ('disabled', 'Disabled'),
            ('not_configured', 'Not Configured'),
        ):
            if int(counts.get(key) or 0) == 1:
                return key, label
    if int(counts.get('disabled') or 0) == total:
        return 'disabled', 'Disabled'
    if ready == 0 and int(counts.get('not_configured') or 0) == 0 and int(counts.get('disabled') or 0) == 0:
        for key, label in (
            ('blocked', 'Blocked'),
            ('degraded', 'Degraded'),
            ('validation_required', 'Validation Required'),
        ):
            if int(counts.get(key) or 0) == configured:
                return key, label
    return 'attention', 'Needs Review'


def build_provider_portfolio_counts(
    *,
    kubernetes_connections: list[KubernetesConnection],
    metrics_sources: list[MetricsSource],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> dict[str, dict[str, int]]:
    counts = {
        'container_orchestrator': portfolio_counts(
            [
                (True, bool(item.integration_instance.enabled), item.readiness_status or 'validation_required')
                for item in kubernetes_connections
            ]
        ),
        'metrics_source': portfolio_counts(
            [(bool(item.endpoint), bool(item.enabled), item.readiness_status) for item in metrics_sources]
        ),
        'alert_source': portfolio_counts(
            [(bool(item.endpoint), bool(item.enabled), item.readiness_status) for item in alertmanager_instances]
        ),
    }
    for integration_type in {item.integration_type for item in extension_instances}:
        targets = [item for item in extension_instances if item.integration_type == integration_type]
        counts[integration_type] = portfolio_counts(
            [(True, bool(item.enabled), item.readiness_status) for item in targets]
        )
    return counts

def load_extension_integration_instances() -> list[IntegrationInstance]:
    integration_types = tuple(
        module.integration_type
        for module in registry.all()
        if module.integration_type not in SPECIALIZED_OVERVIEW_TYPES
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
