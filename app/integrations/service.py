from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from app.cluster.constants import get_environment_label
from app.extensions.db import db
from app.common.presentation import present_user_datetime
from app.models import AlertmanagerInstance, Cluster, PrometheusInstance, Report, ReportSchedule
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.runtime import IntegrationRuntimeObservation
from app.integrations.coverage import build_provider_coverage, bound_source_for_scope
from app.integrations.deletion import kubernetes_deletion_guard
from app.prometheus.repository import cluster_bindings_for_instance


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
    tab: str = "catalog",
    provider: str = "",
    health: str = "",
    readiness: str = "",
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    """Build the Integrations landing page from persisted provider records only.

    The landing page must remain available when no provider has been registered.
    It intentionally avoids provider resolvers, live endpoint calls, and cluster-to-
    provider assumptions so one absent integration cannot break the overview.
    """
    kubernetes_connections = (
        KubernetesConnection.query
        .join(Cluster)
        .order_by(Cluster.created_at.asc(), Cluster.id.asc())
        .all()
    )
    prometheus_instances = PrometheusInstance.query.order_by(PrometheusInstance.name.asc()).all()
    alertmanager_instances = AlertmanagerInstance.query.order_by(AlertmanagerInstance.name.asc()).all()

    stats = _overview_stats(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
    )
    runtime_rows = _runtime_overview_rows(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
    )
    filtered_runtime_rows = runtime_rows
    if provider:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['provider'] == provider]
    if health:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['health_status'] == health]
    if readiness:
        filtered_runtime_rows = [row for row in filtered_runtime_rows if row['readiness'] == readiness]

    page_rows, runtime_pagination = _paginate(filtered_runtime_rows, page=page, per_page=per_page)
    runtime_stats = {
        'total': len(runtime_rows),
        'healthy': sum(1 for row in runtime_rows if row['health_status'] == 'healthy'),
        'degraded': sum(1 for row in runtime_rows if row['health_status'] == 'degraded'),
        'unhealthy': sum(1 for row in runtime_rows if row['health_status'] == 'unhealthy'),
        'not_observed': sum(1 for row in runtime_rows if row['health_status'] == 'not_observed'),
        'capability_attention': sum(1 for row in runtime_rows if row['capability_attention'] > 0),
    }
    catalog = _catalog(
        kubernetes_connections=kubernetes_connections,
        prometheus_instances=prometheus_instances,
        alertmanager_instances=alertmanager_instances,
    )
    return {
        'stats': stats,
        'catalog': catalog,
        'available_provider_count': sum(1 for item in catalog if item['availability'] == 'available'),
        'planned_provider_count': sum(1 for item in catalog if item['availability'] != 'available'),
        'active_tab': tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog',
        'coverage': _coverage(
            kubernetes_connections=kubernetes_connections,
            prometheus_instances=prometheus_instances,
            alertmanager_instances=alertmanager_instances,
        ),
        'runtime_rows': page_rows,
        'runtime_stats': runtime_stats,
        'runtime_pagination': runtime_pagination,
        'runtime_has_targets': bool(runtime_rows),
        'runtime_has_active_filters': bool(provider or health or readiness),
        'selected_provider': provider,
        'selected_health': health,
        'selected_readiness': readiness,
        'provider_options': [
            {'value': 'kubernetes', 'label': 'Kubernetes'},
            {'value': 'prometheus', 'label': 'Prometheus / Thanos'},
            {'value': 'alertmanager', 'label': 'Alertmanager'},
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
    cluster = connection.cluster
    return (
        connection.readiness_status
        or (cluster.kubernetes_readiness_status if cluster else None)
        or 'validation_required'
    )


def _overview_stats(
    *,
    kubernetes_connections: list[KubernetesConnection],
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
) -> dict[str, int]:
    configured = (
        len(kubernetes_connections)
        + sum(1 for instance in prometheus_instances if instance.endpoint)
        + sum(1 for instance in alertmanager_instances if instance.endpoint)
    )
    readiness_values = [
        *(_kubernetes_readiness(connection) for connection in kubernetes_connections),
        *((instance.readiness_status or 'validation_required') for instance in prometheus_instances),
        *((instance.readiness_status or 'validation_required') for instance in alertmanager_instances),
    ]
    ready = sum(1 for value in readiness_values if value == 'ready')
    return {
        'total': len(kubernetes_connections) + len(prometheus_instances) + len(alertmanager_instances),
        'configured': configured,
        'ready': ready,
        'attention': max(configured - ready, 0),
        'blocked': sum(1 for value in readiness_values if value == 'blocked'),
    }


def build_kubernetes_page(*, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    connections = KubernetesConnection.query.join(Cluster).order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    rows = []
    for connection in connections:
        cluster = connection.cluster
        binding_count = IntegrationBinding.query.filter_by(
            integration_instance_id=connection.integration_instance_id,
            enabled=True,
        ).count()
        prometheus, prometheus_binding = bound_source_for_scope(
            'prometheus', scope_type='kubernetes_cluster', scope_key=cluster.id,
        )
        alertmanager, alertmanager_binding = bound_source_for_scope(
            'alertmanager', scope_type='kubernetes_cluster', scope_key=cluster.id,
        )
        rows.append({
            'connection_id': connection.id,
            'integration_instance_id': connection.integration_instance_id,
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'environment': get_environment_label(cluster.environment),
            'server': connection.server or 'Not discovered',
            'readiness': connection.readiness_status or cluster.kubernetes_readiness_status or 'validation_required',
            'compatibility_profile': connection.compatibility_profile or cluster.kubernetes_compatibility_profile,
            'version': cluster.kubernetes_version,
            'binding_count': binding_count,
            'prometheus_instance_id': prometheus.id if prometheus else None,
            'prometheus_name': prometheus.name if prometheus else None,
            'prometheus_binding_status': prometheus_binding.validation_status if prometheus_binding else None,
            'alertmanager_instance_id': alertmanager.id if alertmanager else None,
            'alertmanager_name': alertmanager.name if alertmanager else None,
            'alertmanager_binding_status': alertmanager_binding.validation_status if alertmanager_binding else None,
            'last_validated_at': present_user_datetime(
                connection.last_validated_at or cluster.kubernetes_last_validated_at,
                empty='Not validated',
            ),
        })
    page_rows, pagination = _paginate(rows, page=page, per_page=per_page)
    return {
        'rows': page_rows,
        'pagination': pagination,
        'stats': {
            'total': len(rows),
            'ready': sum(1 for row in rows if row['readiness'] == 'ready'),
            'attention': sum(1 for row in rows if row['readiness'] != 'ready'),
            'bindings': sum(row['binding_count'] for row in rows),
        },
    }


def build_kubernetes_detail(cluster_id: str) -> dict[str, Any] | None:
    from app.integrations.registry import get_integration
    from app.integrations.runtime.presentation import runtime_state_view
    from app.integrations.runtime.repository import list_runtime_history

    connection = (
        KubernetesConnection.query
        .filter_by(cluster_id=cluster_id)
        .first()
    )
    if connection is None:
        return None
    cluster = connection.cluster
    discovery = connection.discovery_summary or cluster.kubernetes_api_discovery_summary or {}
    features = discovery.get('features') or {}
    feature_rows = []
    for key, value in sorted(features.items()):
        selected = value.get('selected_api') or {}
        feature_rows.append({
            'key': key,
            'status': value.get('status') or 'unknown',
            'api_version': (
                f"{selected.get('group')}/{selected.get('version')}"
                if selected.get('group')
                else selected.get('version')
            ) or 'Not selected',
            'resource': selected.get('resource') or '-',
            'stability': selected.get('stability') or '-',
            'message': value.get('message') or '',
        })
    state = get_integration('kubernetes').adapter.get_state(connection)
    capability_scope = next((
        binding.capability_scope or []
        for binding in connection.integration_instance.bindings
        if binding.asset_type == 'kubernetes_cluster' and binding.asset_key == cluster.id
    ), [])
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
    report_count = Report.query.filter(Report.cluster_id == cluster.id).count()
    schedule_count = ReportSchedule.query.filter(ReportSchedule.cluster_id == cluster.id).count()
    deletion_guard = kubernetes_deletion_guard(
        connection_id=connection.id,
        cluster_id=cluster.id,
    )
    source_bindings = [
        {
            'provider': 'Prometheus',
            'icon': 'activity',
            'name': prometheus_source.name if prometheus_source else 'Not bound',
            'status': prometheus_binding.validation_status if prometheus_binding else 'not_bound',
            'role': prometheus_binding.binding_role if prometheus_binding else None,
        },
        {
            'provider': 'Alertmanager',
            'icon': 'siren',
            'name': alertmanager_source.name if alertmanager_source else 'Not bound',
            'status': alertmanager_binding.validation_status if alertmanager_binding else 'not_bound',
            'role': alertmanager_binding.binding_role if alertmanager_binding else None,
        },
    ]
    return {
        'connection': connection,
        'cluster': cluster,
        'canonical': connection.integration_instance,
        'runtime_state': runtime_state_view(state),
        'runtime_history': list_runtime_history('kubernetes', str(connection.id), limit=5),
        'feature_rows': feature_rows,
        'blocked_features': discovery.get('blocked_features') or [],
        'legacy_features': discovery.get('legacy_features') or [],
        'selected_adapters': discovery.get('selected_adapters') or {},
        'capability_scope': capability_scope,
        'source_bindings': source_bindings,
        'deletion_guard': deletion_guard,
        'operational_use': {
            'node_count': int(cluster.node_count or 0),
            'capability_count': len(capability_scope),
            'binding_count': sum(1 for row in source_bindings if row['status'] != 'not_bound'),
            'report_count': report_count,
            'schedule_count': schedule_count,
        },
    }

def build_prometheus_page(
    *,
    query: str = "",
    compatibility: str = "",
    readiness: str = "",
    tab: str = "coverage",
    page: int = 1,
    per_page: int = 5,
    coverage_query: str = "",
    coverage_environment: str = "",
    coverage_status: str = "",
    coverage_page: int = 1,
    coverage_per_page: int = 5,
) -> dict[str, Any]:
    clusters_by_id = {cluster.id: cluster for cluster in Cluster.query.all()}
    all_rows: list[dict[str, Any]] = []
    for instance in PrometheusInstance.query.order_by(PrometheusInstance.name.asc()).all():
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
        all_rows.append({
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
        })

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
        'compatibility_options': _ordered_status_options(all_rows, 'compatibility', ['compatible', 'compatible_with_warnings', 'capability_mismatch', 'unsupported_version', 'version_unknown', 'validation_required']),
        'readiness_options': _ordered_status_options(all_rows, 'readiness', ['ready', 'degraded', 'blocked', 'validation_required']),
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



def _coverage(
    *,
    kubernetes_connections: list[KubernetesConnection],
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
) -> list[dict[str, Any]]:
    observability_instances = [*prometheus_instances, *alertmanager_instances]
    return [
        {
            'key': 'compute',
            'label': 'Compute & Infrastructure',
            'icon': 'boxes',
            'configured': len(kubernetes_connections),
            'ready': sum(1 for item in kubernetes_connections if _kubernetes_readiness(item) == 'ready'),
            'total': len(kubernetes_connections),
        },
        {
            'key': 'observability',
            'label': 'Observability',
            'icon': 'activity',
            'configured': sum(1 for item in observability_instances if item.endpoint),
            'ready': sum(1 for item in observability_instances if item.readiness_status == 'ready'),
            'total': len(observability_instances),
        },
        {'key': 'storage', 'label': 'Storage', 'icon': 'database', 'configured': 0, 'ready': 0, 'total': 0},
        {'key': 'security', 'label': 'Security', 'icon': 'shield-check', 'configured': 0, 'ready': 0, 'total': 0},
    ]


def _catalog(
    *,
    kubernetes_connections: list[KubernetesConnection],
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
) -> list[dict[str, Any]]:
    return [
        {
            'key': 'kubernetes',
            'name': 'Kubernetes',
            'category': 'Compute & Infrastructure',
            'icon': 'boxes',
            'availability': 'available',
            'configured': len(kubernetes_connections),
            'description': 'Canonical Kubernetes API connections, asset identity, discovery, readiness, and operational access.',
        },
        {
            'key': 'prometheus',
            'name': 'Prometheus',
            'category': 'Observability',
            'icon': 'activity',
            'availability': 'available',
            'configured': sum(1 for instance in prometheus_instances if instance.endpoint),
            'description': 'Metrics collection and versioned PromQL validation for connected infrastructure assets.',
        },
        {
            'key': 'alertmanager',
            'name': 'Alertmanager',
            'category': 'Observability',
            'icon': 'siren',
            'availability': 'available',
            'configured': sum(1 for instance in alertmanager_instances if instance.endpoint),
            'description': 'Shared Alertmanager instances, asset bindings, alert retrieval, silence capability, and API compatibility validation.',
        },
        {
            'key': 's3',
            'name': 'S3-compatible Storage',
            'category': 'Storage',
            'icon': 'database',
            'availability': 'planned',
            'configured': 0,
            'description': 'Reusable object storage for reports, archives, and long-term operational evidence.',
        },
        {
            'key': 'vault',
            'name': 'Vault',
            'category': 'Security',
            'icon': 'key-round',
            'availability': 'planned',
            'configured': 0,
            'description': 'External secret and credential management with controlled access and auditability.',
        },
    ]




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


def _runtime_overview_rows(
    *,
    kubernetes_connections: list[KubernetesConnection],
    prometheus_instances: list[PrometheusInstance],
    alertmanager_instances: list[AlertmanagerInstance],
) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], IntegrationRuntimeObservation] = {}
    observations = IntegrationRuntimeObservation.query.order_by(
        IntegrationRuntimeObservation.observed_at.desc(),
        IntegrationRuntimeObservation.id.desc(),
    ).all()
    for observation in observations:
        latest.setdefault((observation.provider, observation.instance_id), observation)

    rows: list[dict[str, Any]] = []
    for connection in kubernetes_connections:
        cluster = connection.cluster
        canonical = db.session.get(IntegrationInstance, connection.integration_instance_id)
        observation = latest.get(('kubernetes', str(connection.id)))
        observed_at = observation.observed_at if observation else (connection.last_validated_at or cluster.kubernetes_last_validated_at)
        rows.append({
            'provider': 'kubernetes',
            'provider_label': 'Kubernetes',
            'instance_id': str(connection.id),
            'cluster_id': str(cluster.id),
            'instance_name': canonical.name if canonical else f'{cluster.name} Kubernetes API',
            'scope_label': cluster.name,
            'endpoint_product': 'Kubernetes API',
            'health_status': observation.health_status if observation else ('healthy' if cluster.status == 'connected' else 'not_observed'),
            'health_score': observation.health_score if observation else None,
            'readiness': connection.readiness_status or cluster.kubernetes_readiness_status or 'validation_required',
            'observed_at': observed_at,
            'observed_at_display': present_user_datetime(observed_at, empty='Not observed'),
            'latency_ms': observation.latency_ms if observation else None,
            'latency_display': f'{observation.latency_ms} ms' if observation and observation.latency_ms is not None else None,
            'capability_profile': connection.compatibility_profile or cluster.kubernetes_compatibility_profile,
            'capability_attention': 0 if (connection.readiness_status or cluster.kubernetes_readiness_status) == 'ready' else 1,
            'capability_attention_display': 'Ready' if (connection.readiness_status or cluster.kubernetes_readiness_status) == 'ready' else 'Validation needs attention',
            'message': (observation.message if observation else None) or connection.validation_message or cluster.kubernetes_validation_message,
        })

    for instance in prometheus_instances:
        observation = latest.get(('prometheus', str(instance.id)))
        assessments = ((instance.capabilities or {}).get('assessments') or [])
        attention = sum(1 for item in assessments if item.get('status') != 'available')
        observed_at = observation.observed_at if observation else instance.last_checked_at
        latency_ms = observation.latency_ms if observation else instance.last_response_time_ms
        enabled_bindings = [binding for binding in instance.integration_instance.bindings if binding.enabled]
        rows.append({
            'provider': 'prometheus',
            'provider_label': 'Prometheus / Thanos',
            'instance_id': str(instance.id),
            'instance_name': instance.name,
            'scope_label': f'{len(enabled_bindings)} asset binding(s)',
            'endpoint_product': (instance.endpoint_product or 'prometheus').replace('_', ' ').title(),
            'health_status': observation.health_status if observation else 'not_observed',
            'health_score': observation.health_score if observation else None,
            'readiness': instance.readiness_status or 'validation_required',
            'observed_at': observed_at,
            'observed_at_display': present_user_datetime(observed_at, empty='Not observed'),
            'latency_ms': latency_ms,
            'latency_display': f'{latency_ms} ms' if latency_ms is not None else None,
            'capability_profile': instance.capability_profile or instance.query_profile,
            'capability_attention': attention,
            'capability_attention_display': (
                f'{attention} item needs attention' if attention == 1 else f'{attention} items need attention'
            ),
            'message': (observation.message if observation else None) or instance.validation_message or instance.last_error,
        })

    for instance in alertmanager_instances:
        observation = latest.get(('alertmanager', str(instance.id)))
        observed_at = observation.observed_at if observation else instance.last_checked_at
        latency_ms = observation.latency_ms if observation else instance.last_response_time_ms
        capability_attention = 0 if instance.capabilities else 1
        rows.append({
            'provider': 'alertmanager',
            'provider_label': 'Alertmanager',
            'instance_id': str(instance.id),
            'instance_name': instance.name,
            'scope_label': f'{len(instance.integration_instance.bindings)} asset binding(s)',
            'endpoint_product': 'Alertmanager',
            'health_status': observation.health_status if observation else 'not_observed',
            'health_score': observation.health_score if observation else None,
            'readiness': instance.readiness_status or 'validation_required',
            'observed_at': observed_at,
            'observed_at_display': present_user_datetime(observed_at, empty='Not observed'),
            'latency_ms': latency_ms,
            'latency_display': f'{latency_ms} ms' if latency_ms is not None else None,
            'capability_profile': instance.capability_profile,
            'capability_attention': capability_attention,
            'capability_attention_display': (
                f'{capability_attention} item needs attention'
                if capability_attention == 1
                else f'{capability_attention} items need attention'
            ),
            'message': (observation.message if observation else None) or instance.validation_message or instance.last_error,
        })

    health_order = {'unhealthy': 0, 'degraded': 1, 'not_observed': 2, 'healthy': 3}
    rows.sort(key=lambda row: (health_order.get(row['health_status'], 2), row['provider_label'], row['instance_name'].lower()))
    return rows
