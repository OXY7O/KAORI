from __future__ import annotations

from typing import Any

from sqlalchemy.orm import contains_eager, selectinload

from app.integrations.overview_extensions import (
    build_extension_runtime_rows,
    build_overview_stats,
    load_extension_integration_instances,
    sort_runtime_rows,
)
from app.integrations.registry import registry
from app.integrations.service import (
    _catalog,
    _coverage,
    _coverage_stats,
    _latest_runtime_observations,
    _paginate,
    _runtime_overview_rows,
    _runtime_scope_label,
    _runtime_stats,
)
from app.models import AlertmanagerInstance, Cluster, PrometheusInstance
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection


def build_integrations_overview(
    *,
    tab: str = 'catalog',
    provider: str = '',
    health: str = '',
    readiness: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    """Build one demand-loaded Integration Overview workspace.

    The landing page remains database-backed and resilient when no provider has
    been registered. Provider resolvers and live endpoint calls remain outside
    this overview; only the selected workspace builds its deeper presentation.
    """
    active_tab = tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog'
    runtime_selected = active_tab == 'runtime'

    kubernetes_query = KubernetesConnection.query.join(KubernetesConnection.cluster).options(
        selectinload(KubernetesConnection.integration_instance)
    )
    if runtime_selected:
        kubernetes_query = kubernetes_query.options(contains_eager(KubernetesConnection.cluster))
    kubernetes_connections = kubernetes_query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()

    prometheus_query = PrometheusInstance.query.join(PrometheusInstance.integration_instance)
    alertmanager_query = AlertmanagerInstance.query.join(AlertmanagerInstance.integration_instance)
    if runtime_selected:
        prometheus_query = prometheus_query.options(
            selectinload(PrometheusInstance.integration_instance).selectinload(IntegrationInstance.bindings)
        )
        alertmanager_query = alertmanager_query.options(
            selectinload(AlertmanagerInstance.integration_instance).selectinload(IntegrationInstance.bindings)
        )
    prometheus_instances = prometheus_query.order_by(IntegrationInstance.name.asc()).all()
    alertmanager_instances = alertmanager_query.order_by(IntegrationInstance.name.asc()).all()
    extension_instances = load_extension_integration_instances()

    modules = registry.all()
    stats = build_overview_stats(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    available_provider_count = len(modules)
    available_domain_count = len({module.domain_key for module in modules})
    context: dict[str, Any] = {
        'stats': stats,
        'available_provider_count': available_provider_count,
        'available_domain_count': available_domain_count,
        'active_tab': active_tab,
    }

    if active_tab == 'catalog':
        context['catalog'] = _catalog(
            kubernetes_connections=kubernetes_connections,
            prometheus_instances=prometheus_instances,
            alertmanager_instances=alertmanager_instances,
            extension_instances=extension_instances,
        )
        return context

    if active_tab == 'coverage':
        coverage = _coverage(
            kubernetes_connections=kubernetes_connections,
            prometheus_instances=prometheus_instances,
            alertmanager_instances=alertmanager_instances,
            extension_instances=extension_instances,
        )
        context['coverage'] = coverage
        context['coverage_stats'] = _coverage_stats(coverage)
        return context

    latest = _latest_runtime_observations()
    runtime_rows = _runtime_overview_rows(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        latest=latest,
    )
    runtime_rows.extend(build_extension_runtime_rows(latest))
    sort_runtime_rows(runtime_rows)
    filtered_runtime_rows = runtime_rows
    if provider:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['provider'] == provider]
    if health:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['health_status'] == health]
    if readiness:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['readiness'] == readiness]

    page_rows, runtime_pagination = _paginate(filtered_runtime_rows, page=page, per_page=per_page)
    runtime_scope_label = _runtime_scope_label(provider=provider, health=health, readiness=readiness)
    context.update(
        {
            'runtime_rows': page_rows,
            'runtime_stats': _runtime_stats(filtered_runtime_rows),
            'runtime_global_stats': _runtime_stats(runtime_rows),
            'runtime_scope_label': runtime_scope_label,
            'runtime_pagination': runtime_pagination,
            'runtime_has_targets': bool(runtime_rows),
            'selected_provider': provider,
            'selected_health': health,
            'selected_readiness': readiness,
            'provider_options': [
                {'value': module.provider_type, 'label': module.runtime_label or module.label} for module in modules
            ],
            'health_options': [
                {'value': 'healthy', 'label': 'Healthy'},
                {'value': 'degraded', 'label': 'Degraded'},
                {'value': 'unhealthy', 'label': 'Unhealthy'},
                {'value': 'not_observed', 'label': 'Not Observed'},
            ],
            'runtime_readiness_options': [
                {'value': 'ready', 'label': 'Ready'},
                {'value': 'degraded', 'label': 'Degraded'},
                {'value': 'blocked', 'label': 'Blocked'},
                {'value': 'validation_required', 'label': 'Validation Required'},
            ],
        }
    )
    return context
