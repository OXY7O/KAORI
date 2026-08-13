from __future__ import annotations

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
from app.integrations.kubernetes.compatibility import FEATURE_CONTRACTS
from app.integrations.kubernetes.messages import compact_readiness_reasons
from app.integrations.overview_extensions import (
    build_extension_runtime_rows,
    build_overview_stats,
    load_extension_integration_instances,
    sort_runtime_rows,
)
from app.integrations.prometheus.scope import cluster_bindings_for_instance
from app.integrations.registry import get_integration, registry
from app.integrations.taxonomy import (
    capability_definitions_for_domain,
    ordered_domain_definitions,
)
from app.models import (
    AlertmanagerInstance,
    Cluster,
    ClusterInventory,
    PrometheusInstance,
    Report,
    ReportSchedule,
)
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.runtime import IntegrationRuntimeObservation


def safe_endpoint(value: str | None) -> str:
    if not value:
        return 'Not configured'
    parsed = urlsplit(value)
    host = parsed.hostname or 'configured endpoint'
    port = f':{parsed.port}' if parsed.port else ''
    path = parsed.path.rstrip('/')
    return f'{parsed.scheme or "http"}://{host}{port}{path}'


def build_integrations_overview(
    *,
    tab: str = 'catalog',
    provider: str = '',
    health: str = '',
    readiness: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    """Build the Integrations landing page from persisted provider records only.

    The landing page must remain available when no provider has been registered.
    It intentionally avoids provider resolvers, live endpoint calls, and cluster-to-
    provider assumptions so one absent integration cannot break the overview.
    """
    kubernetes_connections = (
        KubernetesConnection.query.join(Cluster).order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    )
    prometheus_instances = (
        PrometheusInstance.query.join(PrometheusInstance.integration_instance)
        .order_by(IntegrationInstance.name.asc())
        .all()
    )
    alertmanager_instances = (
        AlertmanagerInstance.query.join(AlertmanagerInstance.integration_instance)
        .order_by(IntegrationInstance.name.asc())
        .all()
    )
    extension_instances = load_extension_integration_instances()

    stats = build_overview_stats(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    runtime_rows = _runtime_overview_rows(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
    )
    runtime_rows.extend(build_extension_runtime_rows(_latest_runtime_observations()))
    sort_runtime_rows(runtime_rows)
    filtered_runtime_rows = runtime_rows
    if provider:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['provider'] == provider]
    if health:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['health_status'] == health]
    if readiness:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['readiness'] == readiness]

    page_rows, runtime_pagination = _paginate(filtered_runtime_rows, page=page, per_page=per_page)
    runtime_global_stats = _runtime_stats(runtime_rows)
    runtime_stats = _runtime_stats(filtered_runtime_rows)
    runtime_scope_label = _runtime_scope_label(
        provider=provider,
        health=health,
        readiness=readiness,
    )
    catalog = _catalog(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    coverage = _coverage(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    return {
        'stats': stats,
        'catalog': catalog,
        'available_provider_count': sum(1 for item in catalog if item['availability'] == 'available'),
        'active_tab': tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog',
        'coverage': coverage,
        'coverage_stats': _coverage_stats(coverage),
        'runtime_rows': page_rows,
        'runtime_stats': runtime_stats,
        'runtime_global_stats': runtime_global_stats,
        'runtime_scope_label': runtime_scope_label,
        'runtime_pagination': runtime_pagination,
        'runtime_has_targets': bool(runtime_rows),
        'runtime_has_active_filters': bool(provider or health or readiness),
        'selected_provider': provider,
        'selected_health': health,
        'selected_readiness': readiness,
        'provider_options': [
            {'value': module.provider_type, 'label': module.runtime_label or module.label} for module in registry.all()
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
            provider='kubernetes',
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
    prometheus_source, prometheus_binding = bound_source_for_scope(
        'prometheus',
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
    )
    alertmanager_source, alertmanager_binding = bound_source_for_scope(
        'alertmanager',
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
        connection_id=connection.id,
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
        'runtime_history': list_runtime_history('kubernetes', str(connection.id), limit=5),
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


def build_prometheus_page(
    *,
    query: str = '',
    compatibility: str = '',
    readiness: str = '',
    tab: str = 'coverage',
    page: int = 1,
    per_page: int = 5,
    coverage_query: str = '',
    coverage_environment: str = '',
    coverage_status: str = '',
    coverage_page: int = 1,
    coverage_per_page: int = 5,
) -> dict[str, Any]:
    clusters_by_id = {cluster.id: cluster for cluster in Cluster.query.all()}
    all_rows: list[dict[str, Any]] = []
    for instance in (
        PrometheusInstance.query.join(PrometheusInstance.integration_instance)
        .order_by(IntegrationInstance.name.asc())
        .all()
    ):
        bindings = cluster_bindings_for_instance(instance, enabled_only=True)
        cluster_ids = [binding.asset_key for binding in bindings]
        bound_clusters = [clusters_by_id[key] for key in cluster_ids if key in clusters_by_id]
        environments = sorted({cluster.environment for cluster in bound_clusters if cluster.environment})
        readiness_value = instance.readiness_status or 'validation_required'
        compatibility_value = instance.compatibility_status or 'validation_required'
        search_text = ' '.join(
            filter(
                None,
                [
                    (instance.name or '').lower(),
                    (instance.description or '').lower(),
                    (instance.endpoint or '').lower(),
                    (instance.endpoint_product or '').lower(),
                    (instance.detected_version or '').lower(),
                    (instance.compatibility_profile or '').lower(),
                    (instance.query_profile or '').lower(),
                ],
            )
        )
        all_rows.append(
            {
                'instance_id': instance.id,
                'name': instance.name,
                'description': instance.description,
                'endpoint': safe_endpoint(instance.endpoint),
                'endpoint_product': instance.endpoint_product or 'prometheus',
                'version': instance.detected_version,
                'compatibility': compatibility_value,
                'readiness': readiness_value,
                'profile': instance.compatibility_profile,
                'query_profile': instance.query_profile,
                'capability_profile': instance.capability_profile,
                'validated_at': present_user_datetime(instance.last_validated_at, empty='Not validated'),
                'binding_count': len(bindings),
                'bound_clusters': bound_clusters,
                'cluster_ids': cluster_ids,
                'environments': environments,
                'configured': bool(instance.endpoint),
                'enabled': instance.enabled,
                'search_text': search_text,
            }
        )

    filtered = all_rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered = [row for row in filtered if normalized_query in row['search_text']]
    if compatibility:
        filtered = [row for row in filtered if row['compatibility'] == compatibility]
    if readiness:
        filtered = [row for row in filtered if row['readiness'] == readiness]
    page_rows, pagination = _paginate(filtered, page=page, per_page=per_page)
    coverage_context = build_provider_coverage(
        'prometheus',
        page=coverage_page,
        per_page=coverage_per_page,
        query=coverage_query,
        environment=coverage_environment,
        status=coverage_status,
    )
    return {
        'rows': page_rows,
        'stats': {
            'total': len(all_rows),
            'configured': len(all_rows),
            'ready': sum(1 for row in all_rows if row['readiness'] == 'ready'),
            'attention': sum(1 for row in all_rows if row['readiness'] != 'ready'),
            'blocked': sum(1 for row in all_rows if row['readiness'] == 'blocked'),
            'bindings': sum(row['binding_count'] for row in all_rows),
        },
        'pagination': pagination,
        **coverage_context,
        'active_tab': tab if tab in {'coverage', 'registry'} else 'coverage',
        'selected_query': query,
        'selected_compatibility': compatibility,
        'selected_readiness': readiness,
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
    from app.alertmanager.presentation import build_inventory_context

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
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> dict[str, dict[str, int]]:
    counts = {
        'kubernetes': {
            'configured': len(kubernetes_connections),
            'ready': sum(1 for item in kubernetes_connections if _kubernetes_readiness(item) == 'ready'),
            'total': len(kubernetes_connections),
        },
        'prometheus': {
            'configured': sum(1 for item in prometheus_instances if item.endpoint),
            'ready': sum(1 for item in prometheus_instances if item.readiness_status == 'ready'),
            'total': len(prometheus_instances),
        },
        'alertmanager': {
            'configured': sum(1 for item in alertmanager_instances if item.endpoint),
            'ready': sum(1 for item in alertmanager_instances if item.readiness_status == 'ready'),
            'total': len(alertmanager_instances),
        },
    }
    for provider_type in {item.provider_type for item in extension_instances}:
        targets = [item for item in extension_instances if item.provider_type == provider_type]
        counts[provider_type] = {
            'configured': len(targets),
            'ready': sum(1 for item in targets if item.readiness_status == 'ready'),
            'total': len(targets),
        }
    return counts


def _coverage(
    *,
    kubernetes_connections: list[KubernetesConnection],
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    provider_counts = _provider_portfolio_counts(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    modules = registry.all()
    rows: list[dict[str, Any]] = []
    for domain in ordered_domain_definitions():
        domain_modules = [module for module in modules if module.domain_key == domain.key]
        lifecycle = 'available' if domain_modules else 'planned'
        counts = [provider_counts.get(module.provider_type, {}) for module in domain_modules]
        configured = sum(int(item.get('configured') or 0) for item in counts)
        ready = sum(int(item.get('ready') or 0) for item in counts)
        total = sum(int(item.get('total') or 0) for item in counts)
        if domain_modules:
            providers = ' · '.join(module.label for module in domain_modules)
        else:
            providers = ' · '.join(capability.label for capability in capability_definitions_for_domain(domain.key))
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
                'attention': max(total - ready, 0) if lifecycle == 'available' else 0,
                'readiness_percent': round((ready / total) * 100, 1) if total else 0.0,
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
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
    extension_instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    provider_counts = _provider_portfolio_counts(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
        extension_instances=extension_instances,
    )
    rows: list[dict[str, Any]] = []
    for module in registry.all():
        counts = provider_counts.get(module.provider_type, {})
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
                'key': module.provider_type,
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


def _runtime_scope_label(*, provider: str, health: str, readiness: str) -> str:
    parts: list[str] = []
    if provider:
        try:
            module = get_integration(provider)
            parts.append(module.runtime_label or module.label)
        except IntegrationNotRegistered:
            parts.append(provider.replace('_', ' ').title())
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


def _latest_runtime_observations() -> dict[tuple[str, str], IntegrationRuntimeObservation]:
    ranked = select(
        IntegrationRuntimeObservation.id.label('observation_id'),
        func.row_number()
        .over(
            partition_by=(
                IntegrationRuntimeObservation.provider,
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
    return {(row.provider, row.instance_id): row for row in observations}


def _runtime_overview_rows(
    *,
    kubernetes_connections: list[KubernetesConnection],
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
) -> list[dict[str, Any]]:
    latest = _latest_runtime_observations()

    rows: list[dict[str, Any]] = []
    for connection in kubernetes_connections:
        cluster = connection.cluster
        canonical = db.session.get(IntegrationInstance, connection.integration_instance_id)
        observation = latest.get(('kubernetes', str(connection.id)))
        validation_at = connection.last_validated_at
        readiness = connection.readiness_status or 'validation_required'
        capability_attention = 0 if readiness == 'ready' else 1
        rows.append(
            {
                'provider': 'kubernetes',
                'provider_label': 'Kubernetes',
                'provider_icon': 'boxes',
                'instance_id': str(connection.id),
                'detail_key': f'kubernetes:{connection.id}',
                'cluster_id': str(cluster.id),
                'instance_name': canonical.name if canonical else f'{cluster.name} Kubernetes API',
                'scope_label': cluster.name,
                'endpoint_product': 'Kubernetes API',
                'connection_status': cluster.status or 'not_observed',
                'health_status': observation.health_status if observation else 'not_observed',
                'health_score': observation.health_score if observation else None,
                'readiness': readiness,
                'observed_at': observation.observed_at if observation else None,
                'observed_at_display': present_user_datetime(
                    observation.observed_at if observation else None,
                    empty='Not observed',
                ),
                'validation_at_display': present_user_datetime(validation_at, empty='Not validated'),
                'latency_ms': observation.latency_ms if observation else None,
                'latency_display': (
                    f'{observation.latency_ms} ms' if observation and observation.latency_ms is not None else None
                ),
                'capability_profile': connection.compatibility_profile,
                'capability_attention': capability_attention,
                'capability_attention_display': _capability_attention_display(capability_attention),
                'message': (observation.message if observation else None) or connection.validation_message,
            }
        )

    for instance in prometheus_instances:
        observation = latest.get(('prometheus', str(instance.id)))
        assessments = (instance.capabilities or {}).get('assessments') or []
        attention = sum(1 for item in assessments if item.get('status') != 'available')
        validation_at = instance.last_checked_at or instance.last_validated_at
        enabled_bindings = [binding for binding in instance.integration_instance.bindings if binding.enabled]
        rows.append(
            {
                'provider': 'prometheus',
                'provider_label': 'Prometheus',
                'provider_icon': 'activity',
                'instance_id': str(instance.id),
                'detail_key': f'prometheus:{instance.id}',
                'instance_name': instance.name,
                'scope_label': f'{len(enabled_bindings)} asset binding(s)',
                'endpoint_product': (instance.endpoint_product or 'prometheus').replace('_', ' ').title(),
                'connection_status': instance.last_status or 'not_observed',
                'health_status': observation.health_status if observation else 'not_observed',
                'health_score': observation.health_score if observation else None,
                'readiness': instance.readiness_status or 'validation_required',
                'observed_at': observation.observed_at if observation else None,
                'observed_at_display': present_user_datetime(
                    observation.observed_at if observation else None,
                    empty='Not observed',
                ),
                'validation_at_display': present_user_datetime(validation_at, empty='Not validated'),
                'latency_ms': observation.latency_ms if observation else None,
                'latency_display': (
                    f'{observation.latency_ms} ms' if observation and observation.latency_ms is not None else None
                ),
                'capability_profile': instance.capability_profile or instance.query_profile,
                'capability_attention': attention,
                'capability_attention_display': _capability_attention_display(attention),
                'message': (observation.message if observation else None)
                or instance.validation_message
                or instance.last_error,
            }
        )

    for instance in alertmanager_instances:
        observation = latest.get(('alertmanager', str(instance.id)))
        validation_at = instance.last_checked_at or instance.last_validated_at
        capability_attention = 0 if instance.capabilities else 1
        enabled_bindings = [binding for binding in instance.integration_instance.bindings if binding.enabled]
        rows.append(
            {
                'provider': 'alertmanager',
                'provider_label': 'Alertmanager',
                'provider_icon': 'siren',
                'instance_id': str(instance.id),
                'detail_key': f'alertmanager:{instance.id}',
                'instance_name': instance.name,
                'scope_label': f'{len(enabled_bindings)} asset binding(s)',
                'endpoint_product': 'Alertmanager',
                'connection_status': instance.last_status or 'not_observed',
                'health_status': observation.health_status if observation else 'not_observed',
                'health_score': observation.health_score if observation else None,
                'readiness': instance.readiness_status or 'validation_required',
                'observed_at': observation.observed_at if observation else None,
                'observed_at_display': present_user_datetime(
                    observation.observed_at if observation else None,
                    empty='Not observed',
                ),
                'validation_at_display': present_user_datetime(validation_at, empty='Not validated'),
                'latency_ms': observation.latency_ms if observation else None,
                'latency_display': (
                    f'{observation.latency_ms} ms' if observation and observation.latency_ms is not None else None
                ),
                'capability_profile': instance.capability_profile,
                'capability_attention': capability_attention,
                'capability_attention_display': _capability_attention_display(capability_attention),
                'message': (observation.message if observation else None)
                or instance.validation_message
                or instance.last_error,
            }
        )

    sort_runtime_rows(rows)
    return rows


def build_integration_runtime_detail(provider: str, instance_id: str) -> dict[str, Any] | None:
    try:
        target_id = int(instance_id)
    except (TypeError, ValueError):
        return None
    known = {
        'kubernetes': (KubernetesConnection, 'kubernetes_connections'),
        'prometheus': (PrometheusInstance, 'prometheus_instances'),
        'alertmanager': (AlertmanagerInstance, 'alertmanager_instances'),
    }
    if provider in known:
        model, collection_key = known[provider]
        target = db.session.get(model, target_id)
        if target is None:
            return None
        runtime_args: dict[str, Any] = {
            'kubernetes_connections': [],
            'prometheus_instances': [],
            'alertmanager_instances': [],
        }
        runtime_args[collection_key] = [target]
        rows = _runtime_overview_rows(**runtime_args)
    else:
        try:
            module = get_integration(provider)
        except IntegrationNotRegistered:
            return None
        if module.runtime_overview_builder is None:
            return None
        rows = module.runtime_overview_builder(_latest_runtime_observations(), target_id)
    return rows[0] if rows else None
