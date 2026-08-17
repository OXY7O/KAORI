from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select

from app.common.presentation import present_key_label, present_user_datetime
from app.extensions.db import db
from app.integrations.asset_owner_sources import build_bound_observability_source_rows
from app.integrations.contracts import IntegrationNotRegistered
from app.integrations.coverage import (
    bound_source_for_scope,
    build_provider_coverage,
)
from app.integrations.deletion import kubernetes_deletion_guard
from app.integrations.observability.metrics_source.providers import provider_definition, provider_options
from app.integrations.observability.metrics_source.scope import cluster_bindings_for_instance
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.compatibility import (
    FEATURE_CONTRACTS,
)
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.messages import (
    compact_readiness_reasons,
)
from app.integrations.overview_extensions import sort_runtime_rows
from app.integrations.provider_matrix import provider_kind
from app.integrations.registry import get_integration, registry
from app.integrations.taxonomy import (
    capability_definitions_for_domain,
    ordered_domain_definitions,
)
from app.models import (
    AlertmanagerInstance,
    Cluster,
    ClusterInventory,
    MetricsSource,
    Report,
    ReportSchedule,
)
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.runtime import IntegrationRuntimeObservation


@dataclass(frozen=True, slots=True)
class MetricsSourceRegistryFilters:
    query: str = ''
    provider_key: str = ''
    compatibility: str = ''
    readiness: str = ''
    page: int = 1
    per_page: int = 5


def safe_endpoint(value: str | None) -> str:
    if not value:
        return 'Not configured'
    parsed = urlsplit(value)
    host = parsed.hostname or 'configured endpoint'
    port = f':{parsed.port}' if parsed.port else ''
    path = parsed.path.rstrip('/')
    return f'{parsed.scheme or "http"}://{host}{port}{path}'


def _kubernetes_readiness(connection: KubernetesConnection) -> str:
    return connection.readiness_status or 'validation_required'


def build_kubernetes_capability_registry(
    feature_rows: list[dict[str, Any]],
    *,
    query: str = '',
    requirement: str = '',
    status: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    """Filter and paginate Kubernetes capability rows for the HTMX registry.

    Capability Registry interactions intentionally follow the same server-backed
    loading contract as Recent Runtime Observations: filters and pagination issue
    an HTMX request, the shared loading bar is the request indicator, and the
    server returns the canonical filtered page.
    """
    normalized_query = str(query or '').strip().lower()
    normalized_requirement = str(requirement or '').strip().lower()
    normalized_status = str(status or '').strip().lower()

    if normalized_requirement not in {'required', 'optional'}:
        normalized_requirement = ''
    if normalized_status not in {'ready', 'legacy', 'blocked'}:
        normalized_status = ''

    filtered_rows = list(feature_rows)
    if normalized_query:
        filtered_rows = [
            row
            for row in filtered_rows
            if normalized_query
            in ' '.join(
                str(value or '')
                for value in (
                    row.get('key'),
                    row.get('resource'),
                    row.get('api_version'),
                    row.get('stability'),
                    row.get('requirement_label'),
                    row.get('status'),
                )
            ).lower()
        ]
    if normalized_requirement:
        filtered_rows = [
            row
            for row in filtered_rows
            if ('required' if row.get('required') else 'optional') == normalized_requirement
        ]
    if normalized_status:
        filtered_rows = [row for row in filtered_rows if row.get('status') == normalized_status]

    page_rows, pagination = _paginate(filtered_rows, page=page, per_page=per_page)
    return {
        'rows': page_rows,
        'pagination': pagination,
        'filters': {
            'query': normalized_query,
            'requirement': normalized_requirement,
            'status': normalized_status,
        },
        'total_contracts': len(feature_rows),
    }


def build_kubernetes_detail(cluster_id: str) -> dict[str, Any] | None:
    from app.integrations.runtime.presentation import runtime_observation_state_view
    from app.integrations.runtime.repository import list_runtime_history

    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first()
    if connection is None:
        return None
    cluster = connection.cluster
    discovery = connection.discovery_summary or {}
    features = discovery.get('features') or {}
    feature_contracts = {contract.key: contract for contract in FEATURE_CONTRACTS}
    feature_rows = []
    for key, value in sorted(features.items()):
        selected = value.get('selected_api') or {}
        contract = feature_contracts.get(key)
        required = bool(value.get('required', contract.required if contract else True))
        required_verbs = tuple(
            value.get('required_verbs') or (contract.required_verbs if contract else ('get', 'list'))
        )
        feature_rows.append(
            {
                'key': key,
                'status': value.get('status') or 'unknown',
                'api_version': (
                    f'{selected.get("group")}/{selected.get("version")}'
                    if selected.get('group')
                    else selected.get('version')
                )
                or 'Not selected',
                'resource': selected.get('resource') or '-',
                'stability': selected.get('stability') or '-',
                'message': value.get('message') or '',
                'required': required,
                'requirement_label': 'Required' if required else 'Optional',
                'required_verbs': required_verbs,
                'required_verbs_display': ', '.join(required_verbs) if required_verbs else 'None',
            }
        )
    selected_adapters = discovery.get('selected_adapters') or {}
    latest_runtime_observation = (
        IntegrationRuntimeObservation.query.filter_by(
            integration_type='container_orchestrator',
            instance_id=str(connection.id),
        )
        .order_by(
            IntegrationRuntimeObservation.observed_at.desc(),
            IntegrationRuntimeObservation.id.desc(),
        )
        .first()
    )
    runtime_state = runtime_observation_state_view(
        latest_runtime_observation,
        fallback_readiness=connection.readiness_status or 'validation_required',
        fallback_compatibility_profile=connection.compatibility_profile,
        fallback_capabilities=tuple(selected_adapters.keys()),
    )
    capability_scope = next(
        (
            binding.capability_scope or []
            for binding in connection.integration_instance.bindings
            if binding.asset_type == 'kubernetes_cluster' and binding.asset_key == cluster.id
        ),
        [],
    )
    metrics_source, metrics_binding = bound_source_for_scope(
        'metrics_source',
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
    )
    alertmanager_source, alertmanager_binding = bound_source_for_scope(
        'alert_source',
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
    )
    latest_inventory = (
        ClusterInventory.query.filter_by(cluster_id=cluster.id)
        .order_by(ClusterInventory.collected_at.desc(), ClusterInventory.id.desc())
        .first()
    )
    report_count = Report.query.filter(Report.cluster_id == cluster.id).count()
    schedule_count = ReportSchedule.query.filter(ReportSchedule.cluster_id == cluster.id).count()
    deletion_guard = kubernetes_deletion_guard(
        integration_instance_id=connection.integration_instance_id,
        cluster_id=cluster.id,
    )
    source_bindings = build_bound_observability_source_rows(
        asset_type='kubernetes_cluster',
        asset_key=cluster.id,
    )
    return {
        'connection': connection,
        'cluster': cluster,
        'canonical': connection.integration_instance,
        'runtime_state': runtime_state,
        'validation_state': {
            'readiness': connection.readiness_status or 'validation_required',
            'readiness_label': present_key_label(connection.readiness_status or 'validation_required'),
            'message': ' '.join(compact_readiness_reasons(discovery.get('readiness_reasons') or []))
            or 'Run Full Validation to refresh API, compatibility, and RBAC evidence.',
        },
        'runtime_history': list_runtime_history('container_orchestrator', str(connection.id), limit=5),
        'feature_rows': feature_rows,
        'blocked_features': discovery.get('blocked_features') or [],
        'legacy_features': discovery.get('legacy_features') or [],
        'optional_blocked_features': discovery.get('optional_blocked_features') or [],
        'optional_legacy_features': discovery.get('optional_legacy_features') or [],
        'selected_adapters': selected_adapters,
        'capability_scope': capability_scope,
        'source_bindings': source_bindings,
        'deletion_guard': deletion_guard,
        'validated_feature_count': len(selected_adapters),
        'operational_domain_count': len(capability_scope),
        'operational_use': {
            'node_count': int(cluster.node_count or 0),
            'validated_feature_count': len(selected_adapters),
            'operational_domain_count': len(capability_scope),
            'binding_count': sum(1 for row in source_bindings if row['binding_validation'] != 'not_bound'),
            'report_count': report_count,
            'schedule_count': schedule_count,
            'inventory_status': 'committed' if latest_inventory else 'not_collected',
            'inventory_status_label': 'Committed Snapshot' if latest_inventory else 'No Committed Inventory',
            'inventory_collected_at': latest_inventory.collected_at if latest_inventory else None,
            'inventory_collected_at_display': present_user_datetime(
                latest_inventory.collected_at if latest_inventory else None,
                empty='Never',
                include_seconds=True,
            ),
        },
    }


def build_metrics_source_page(
    *,
    filters: MetricsSourceRegistryFilters | None = None,
    tab: str = 'coverage',
    coverage_query: str = '',
    coverage_environment: str = '',
    coverage_status: str = '',
    coverage_page: int = 1,
    coverage_per_page: int = 5,
) -> dict[str, Any]:
    filters = filters or MetricsSourceRegistryFilters()
    all_rows = _metrics_source_registry_rows()
    filtered = _filter_metrics_source_registry_rows(all_rows, filters)
    page_rows, pagination = _paginate(filtered, page=filters.page, per_page=filters.per_page)
    coverage_context = build_provider_coverage(
        'metrics_source',
        page=coverage_page,
        per_page=coverage_per_page,
        query=coverage_query,
        environment=coverage_environment,
        status=coverage_status,
    )
    return {
        'rows': page_rows,
        'stats': _metrics_source_registry_stats(all_rows),
        'pagination': pagination,
        **coverage_context,
        'active_tab': tab if tab in {'coverage', 'registry'} else 'coverage',
        'selected_query': filters.query,
        'selected_provider_key': filters.provider_key,
        'provider_options': provider_options(),
        'selected_compatibility': filters.compatibility,
        'selected_readiness': filters.readiness,
        'compatibility_options': _ordered_status_options(
            all_rows,
            'compatibility',
            [
                'compatible',
                'compatible_with_warnings',
                'capability_mismatch',
                'unsupported_version',
                'version_unknown',
                'validation_required',
            ],
        ),
        'readiness_options': _ordered_status_options(
            all_rows, 'readiness', ['ready', 'degraded', 'blocked', 'validation_required']
        ),
    }


def _metrics_source_registry_rows() -> list[dict[str, Any]]:
    clusters_by_id = {cluster.id: cluster for cluster in Cluster.query.all()}
    rows: list[dict[str, Any]] = []
    instances = (
        MetricsSource.query.join(MetricsSource.integration_instance).order_by(IntegrationInstance.name.asc()).all()
    )
    for instance in instances:
        bindings = cluster_bindings_for_instance(instance, enabled_only=True)
        cluster_ids = [binding.asset_key for binding in bindings]
        bound_clusters = [clusters_by_id[key] for key in cluster_ids if key in clusters_by_id]
        provider = provider_definition(instance.provider_key)
        rows.append(
            {
                'instance_id': instance.id,
                'name': instance.name,
                'description': instance.description,
                'endpoint': safe_endpoint(instance.endpoint),
                'provider_key': provider.key,
                'provider_label': provider.label,
                'provider_icon': provider.icon,
                'adapter_key': instance.adapter_key,
                'query_language': instance.query_language,
                'endpoint_product': instance.endpoint_product or provider.key,
                'version': instance.detected_version,
                'compatibility': instance.compatibility_status or 'validation_required',
                'readiness': instance.readiness_status or 'validation_required',
                'profile': instance.compatibility_profile,
                'query_profile': instance.query_profile,
                'capability_profile': instance.capability_profile,
                'validated_at': present_user_datetime(instance.last_validated_at, empty='Not validated'),
                'binding_count': len(bindings),
                'bound_clusters': bound_clusters,
                'cluster_ids': cluster_ids,
                'environments': sorted({cluster.environment for cluster in bound_clusters if cluster.environment}),
                'configured': bool(instance.endpoint),
                'enabled': instance.enabled,
                'search_text': _metrics_source_search_text(instance, provider.key, provider.label),
            }
        )
    return rows


def _metrics_source_search_text(instance: MetricsSource, provider_key: str, provider_label: str) -> str:
    return ' '.join(
        filter(
            None,
            [
                (instance.name or '').lower(),
                (instance.description or '').lower(),
                (instance.endpoint or '').lower(),
                provider_key.lower(),
                provider_label.lower(),
                (instance.adapter_key or '').lower(),
                (instance.query_language or '').lower(),
                (instance.endpoint_product or '').lower(),
                (instance.detected_version or '').lower(),
                (instance.compatibility_profile or '').lower(),
                (instance.query_profile or '').lower(),
            ],
        )
    )


def _filter_metrics_source_registry_rows(
    rows: list[dict[str, Any]],
    filters: MetricsSourceRegistryFilters,
) -> list[dict[str, Any]]:
    filtered = rows
    query = filters.query.strip().lower()
    if query:
        filtered = [row for row in filtered if query in row['search_text']]
    if filters.provider_key:
        filtered = [row for row in filtered if row['provider_key'] == filters.provider_key]
    if filters.compatibility:
        filtered = [row for row in filtered if row['compatibility'] == filters.compatibility]
    if filters.readiness:
        filtered = [row for row in filtered if row['readiness'] == filters.readiness]
    return filtered


def _metrics_source_registry_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'total': len(rows),
        'configured': len(rows),
        'ready': sum(1 for row in rows if row['readiness'] == 'ready'),
        'attention': sum(1 for row in rows if row['readiness'] != 'ready'),
        'blocked': sum(1 for row in rows if row['readiness'] == 'blocked'),
        'bindings': sum(row['binding_count'] for row in rows),
    }


def build_alertmanager_page(
    *,
    query: str = '',
    compatibility: str = '',
    readiness: str = '',
    deployment_type: str = '',
    tab: str = 'coverage',
    page: int = 1,
    per_page: int = 5,
    coverage_query: str = '',
    coverage_environment: str = '',
    coverage_status: str = '',
    coverage_page: int = 1,
    coverage_per_page: int = 5,
) -> dict[str, Any]:
    from app.alert_sources.providers.alertmanager.presentation import build_inventory_context

    return build_inventory_context(
        query=query,
        compatibility=compatibility,
        readiness=readiness,
        deployment_type=deployment_type,
        tab=tab,
        page=page,
        per_page=per_page,
        coverage_query=coverage_query,
        coverage_environment=coverage_environment,
        coverage_status=coverage_status,
        coverage_page=coverage_page,
        coverage_per_page=coverage_per_page,
    )


def _provider_portfolio_counts(
    *,
    kubernetes_connections: list[KubernetesConnection],
    metrics_sources: list[MetricsSource],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> dict[str, dict[str, int]]:
    counts = {
        'container_orchestrator': {
            'configured': len(kubernetes_connections),
            'ready': sum(
                1
                for item in kubernetes_connections
                if item.integration_instance.enabled and _kubernetes_readiness(item) == 'ready'
            ),
            'total': len(kubernetes_connections),
        },
        'metrics_source': {
            'configured': sum(1 for item in metrics_sources if item.endpoint),
            'ready': sum(1 for item in metrics_sources if item.enabled and item.readiness_status == 'ready'),
            'total': len(metrics_sources),
        },
        'alert_source': {
            'configured': sum(1 for item in alertmanager_instances if item.endpoint),
            'ready': sum(1 for item in alertmanager_instances if item.enabled and item.readiness_status == 'ready'),
            'total': len(alertmanager_instances),
        },
    }
    for integration_type in {item.integration_type for item in extension_instances}:
        targets = [item for item in extension_instances if item.integration_type == integration_type]
        counts[integration_type] = {
            'configured': len(targets),
            'ready': sum(1 for item in targets if item.enabled and item.readiness_status == 'ready'),
            'total': len(targets),
        }
    return counts


def _coverage(
    *,
    kubernetes_connections: list[KubernetesConnection],
    metrics_sources: list[MetricsSource],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    provider_counts = _provider_portfolio_counts(
        kubernetes_connections=kubernetes_connections,
        metrics_sources=metrics_sources,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    modules = registry.all()
    rows: list[dict[str, Any]] = []
    for domain in ordered_domain_definitions():
        domain_modules = [module for module in modules if module.domain_key == domain.key]
        lifecycle = 'available' if domain_modules else 'planned'
        counts = [provider_counts.get(module.integration_type, {}) for module in domain_modules]
        configured = sum(int(item.get('configured') or 0) for item in counts)
        ready = sum(int(item.get('ready') or 0) for item in counts)
        total = sum(int(item.get('total') or 0) for item in counts)
        if domain_modules:
            providers = ' · '.join(module.label for module in domain_modules)
        else:
            providers = ' · '.join(capability.label for capability in capability_definitions_for_domain(domain.key))
        attention = max(total - ready, 0) if lifecycle == 'available' else 0
        if lifecycle != 'available':
            posture_state, posture_label = 'planned', 'Planned'
        elif total <= 0:
            posture_state, posture_label = 'not_configured', 'Not Configured'
        elif attention > 0:
            posture_state, posture_label = 'validation_required', 'Needs Review'
        else:
            posture_state, posture_label = 'ready', 'Ready'
        rows.append(
            {
                'key': domain.key,
                'label': domain.label,
                'description': domain.description,
                'icon': domain.icon,
                'providers': providers or 'No Providers Registered',
                'configured': configured,
                'ready': ready,
                'total': total,
                'lifecycle': lifecycle,
                'attention': attention,
                'readiness_percent': round((ready / total) * 100, 1) if total else 0.0,
                'posture_state': posture_state,
                'posture_label': posture_label,
            }
        )
    return rows


def _coverage_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    available = [row for row in rows if row['lifecycle'] == 'available']
    return {
        'available_domains': len(available),
        'planned_domains': sum(1 for row in rows if row['lifecycle'] != 'available'),
        'configured_targets': sum(row['configured'] for row in available),
        'ready_targets': sum(row['ready'] for row in available),
        'attention_targets': sum(row['attention'] for row in available),
    }


def _catalog(
    *,
    kubernetes_connections: list[KubernetesConnection],
    metrics_sources: list[MetricsSource],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    provider_counts = _provider_portfolio_counts(
        kubernetes_connections=kubernetes_connections,
        metrics_sources=metrics_sources,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    rows: list[dict[str, Any]] = []
    for module in registry.all():
        counts = provider_counts.get(module.integration_type, {})
        configured = int(counts.get('configured') or 0)
        ready = int(counts.get('ready') or 0)
        total = int(counts.get('total') or 0)
        attention = max(total - ready, 0)
        if total <= 0:
            posture_state = 'not_configured'
            posture_label = 'Not Configured'
        elif attention > 0:
            posture_state = 'validation_required'
            posture_label = 'Needs Review'
        else:
            posture_state = 'ready'
            posture_label = 'Ready'
        rows.append(
            {
                'key': module.integration_type,
                'name': module.label,
                'category': module.domain.label,
                'capability': module.capability.label,
                'icon': module.icon,
                'availability': 'available',
                'configured': configured,
                'ready': ready,
                'total': total,
                'attention': attention,
                'readiness_percent': round((ready / total) * 100, 1) if total else 0.0,
                'posture_state': posture_state,
                'posture_label': posture_label,
                'description': module.description,
                'workspace_endpoint': module.workspace_endpoint,
            }
        )
    return rows


def _ordered_status_options(rows: list[dict[str, Any]], field: str, order: list[str]) -> list[str]:
    values = {row[field] for row in rows if row.get(field)}
    return [value for value in order if value in values] + sorted(values - set(order))


def _paginate(
    rows: list[dict[str, Any]],
    *,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed_per_page = [5, 10, 25, 50]
    if per_page not in allowed_per_page:
        per_page = allowed_per_page[0]
    page = max(page, 1)
    total_items = len(rows)
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    return rows[start_index:end_index], {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start_index + 1 if total_items else 0,
        'end_item': min(end_index, total_items),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed_per_page,
    }


def _runtime_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'total': len(rows),
        'healthy': sum(1 for row in rows if row['health_status'] == 'healthy'),
        'degraded': sum(1 for row in rows if row['health_status'] == 'degraded'),
        'unhealthy': sum(1 for row in rows if row['health_status'] == 'unhealthy'),
        'not_observed': sum(1 for row in rows if row['health_status'] == 'not_observed'),
        'capability_attention': sum(1 for row in rows if row['capability_attention'] > 0),
    }


def _runtime_scope_label(*, integration_type: str, health: str, readiness: str) -> str:
    parts: list[str] = []
    if integration_type:
        try:
            module = get_integration(integration_type)
            parts.append(module.runtime_label or module.label)
        except IntegrationNotRegistered:
            parts.append(integration_type.replace('_', ' ').title())
    if health:
        parts.append(health.replace('_', ' ').title())
    if readiness:
        parts.append(readiness.replace('_', ' ').title())
    return ' · '.join(parts) if parts else 'All Registered Targets'


def _capability_attention_display(count: int) -> str:
    if count <= 0:
        return 'No Capability Attention'
    if count == 1:
        return '1 Item Needs Attention'
    return f'{count} Items Need Attention'


def _latest_runtime_observation(integration_type: str, instance_id: str) -> IntegrationRuntimeObservation | None:
    return (
        IntegrationRuntimeObservation.query.filter_by(integration_type=integration_type, instance_id=instance_id)
        .order_by(
            IntegrationRuntimeObservation.observed_at.desc(),
            IntegrationRuntimeObservation.id.desc(),
        )
        .first()
    )


def _latest_runtime_observations() -> dict[tuple[str, str], IntegrationRuntimeObservation]:
    ranked = select(
        IntegrationRuntimeObservation.id.label('observation_id'),
        func.row_number()
        .over(
            partition_by=(
                IntegrationRuntimeObservation.integration_type,
                IntegrationRuntimeObservation.instance_id,
            ),
            order_by=(
                IntegrationRuntimeObservation.observed_at.desc(),
                IntegrationRuntimeObservation.id.desc(),
            ),
        )
        .label('row_number'),
    ).subquery()
    statement = (
        select(IntegrationRuntimeObservation)
        .join(ranked, ranked.c.observation_id == IntegrationRuntimeObservation.id)
        .where(ranked.c.row_number == 1)
    )
    observations = db.session.execute(statement).scalars().all()
    return {(row.integration_type, row.instance_id): row for row in observations}


def _runtime_overview_rows(
    *,
    kubernetes_connections: list[KubernetesConnection],
    metrics_sources: list[MetricsSource],
    alertmanager_instances: list[AlertmanagerInstance],
    latest: Mapping[tuple[str, str], IntegrationRuntimeObservation],
) -> list[dict[str, Any]]:
    rows = [
        *[_kubernetes_runtime_row(item, latest) for item in kubernetes_connections],
        *[_metrics_source_runtime_row(item, latest) for item in metrics_sources],
        *[_alertmanager_runtime_row(item, latest) for item in alertmanager_instances],
    ]
    sort_runtime_rows(rows)
    return rows


def _kubernetes_runtime_row(
    connection: KubernetesConnection,
    latest: Mapping[tuple[str, str], IntegrationRuntimeObservation],
) -> dict[str, Any]:
    cluster = connection.cluster
    canonical = connection.integration_instance
    observation = latest.get(('container_orchestrator', str(connection.id)))
    readiness = connection.readiness_status or 'validation_required'
    capability_attention = 0 if readiness == 'ready' else 1
    provider = provider_kind('container_orchestrator', canonical.provider_key)
    return {
        'integration_type': 'container_orchestrator',
        'provider_key': provider.key,
        'adapter_key': canonical.adapter_key,
        'provider_label': provider.label,
        'provider_icon': 'boxes',
        'instance_id': str(connection.id),
        'detail_key': f'container_orchestrator:{connection.id}',
        'cluster_id': str(cluster.id),
        'instance_name': canonical.name if canonical else f'{cluster.name} Kubernetes API',
        'scope_label': cluster.name,
        'endpoint_product': 'Kubernetes API',
        'connection_status': cluster.status or 'not_observed',
        **_runtime_observation_fields(observation),
        'readiness': readiness,
        'validation_at_display': present_user_datetime(connection.last_validated_at, empty='Not validated'),
        'capability_profile': connection.compatibility_profile,
        'capability_attention': capability_attention,
        'capability_attention_display': _capability_attention_display(capability_attention),
        'message': (observation.message if observation else None) or connection.validation_message,
    }


def _metrics_source_runtime_row(
    instance: MetricsSource,
    latest: Mapping[tuple[str, str], IntegrationRuntimeObservation],
) -> dict[str, Any]:
    observation = latest.get(('metrics_source', str(instance.id)))
    assessments = (instance.capabilities or {}).get('assessments') or []
    attention = sum(1 for item in assessments if item.get('status') != 'available')
    enabled_bindings = [binding for binding in instance.integration_instance.bindings if binding.enabled]
    provider = provider_definition(instance.provider_key)
    return {
        'integration_type': 'metrics_source',
        'provider_label': provider.label,
        'provider_icon': provider.icon,
        'instance_id': str(instance.id),
        'detail_key': f'metrics_source:{instance.id}',
        'instance_name': instance.name,
        'scope_label': f'{len(enabled_bindings)} asset binding(s)',
        'endpoint_product': (instance.endpoint_product or provider.key).replace('_', ' ').title(),
        'provider_key': provider.key,
        'adapter_key': instance.adapter_key,
        'query_language': instance.query_language,
        'connection_status': instance.last_status or 'not_observed',
        **_runtime_observation_fields(observation),
        'readiness': instance.readiness_status or 'validation_required',
        'validation_at_display': present_user_datetime(
            instance.last_checked_at or instance.last_validated_at,
            empty='Not validated',
        ),
        'capability_profile': instance.capability_profile or instance.query_profile,
        'capability_attention': attention,
        'capability_attention_display': _capability_attention_display(attention),
        'message': (observation.message if observation else None) or instance.validation_message or instance.last_error,
    }


def _alertmanager_runtime_row(
    instance: AlertmanagerInstance,
    latest: Mapping[tuple[str, str], IntegrationRuntimeObservation],
) -> dict[str, Any]:
    observation = latest.get(('alert_source', str(instance.id)))
    capability_attention = 0 if instance.capabilities else 1
    enabled_bindings = [binding for binding in instance.integration_instance.bindings if binding.enabled]
    canonical = instance.integration_instance
    provider = provider_kind('alert_source', canonical.provider_key)
    return {
        'integration_type': 'alert_source',
        'provider_key': provider.key,
        'adapter_key': canonical.adapter_key,
        'provider_label': provider.label,
        'provider_icon': 'siren',
        'instance_id': str(instance.id),
        'detail_key': f'alert_source:{instance.id}',
        'instance_name': instance.name,
        'scope_label': f'{len(enabled_bindings)} asset binding(s)',
        'endpoint_product': 'Alertmanager',
        'connection_status': instance.last_status or 'not_observed',
        **_runtime_observation_fields(observation),
        'readiness': instance.readiness_status or 'validation_required',
        'validation_at_display': present_user_datetime(
            instance.last_checked_at or instance.last_validated_at,
            empty='Not validated',
        ),
        'capability_profile': instance.capability_profile,
        'capability_attention': capability_attention,
        'capability_attention_display': _capability_attention_display(capability_attention),
        'message': (observation.message if observation else None) or instance.validation_message or instance.last_error,
    }


def _runtime_observation_fields(observation: IntegrationRuntimeObservation | None) -> dict[str, Any]:
    latency_ms = observation.latency_ms if observation else None
    return {
        'health_status': observation.health_status if observation else 'not_observed',
        'health_score': observation.health_score if observation else None,
        'observed_at': observation.observed_at if observation else None,
        'observed_at_display': present_user_datetime(
            observation.observed_at if observation else None,
            empty='Not observed',
        ),
        'latency_ms': latency_ms,
        'latency_display': f'{latency_ms} ms' if latency_ms is not None else None,
    }


def build_integration_runtime_detail(integration_type: str, instance_id: str) -> dict[str, Any] | None:
    try:
        target_id = int(instance_id)
    except (TypeError, ValueError):
        return None
    known = {
        'container_orchestrator': (KubernetesConnection, 'kubernetes_connections'),
        'metrics_source': (MetricsSource, 'metrics_sources'),
        'alert_source': (AlertmanagerInstance, 'alertmanager_instances'),
    }
    if integration_type in known:
        model, collection_key = known[integration_type]
        target = db.session.get(model, target_id)
        if target is None:
            return None
        runtime_args: dict[str, Any] = {
            'kubernetes_connections': [],
            'metrics_sources': [],
            'alertmanager_instances': [],
        }
        runtime_args[collection_key] = [target]
        observation = _latest_runtime_observation(integration_type, str(target_id))
        latest = {(integration_type, str(target_id)): observation} if observation is not None else {}
        rows = _runtime_overview_rows(**runtime_args, latest=latest)
    else:
        try:
            module = get_integration(integration_type)
        except IntegrationNotRegistered:
            return None
        observation = _latest_runtime_observation(integration_type, str(target_id))
        latest = {(integration_type, str(target_id)): observation} if observation is not None else {}
        rows = module.build_runtime_overview_rows(latest, target_id)
    return rows[0] if rows else None
