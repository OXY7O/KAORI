from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from app.cluster.constants import get_environment_label
from app.extensions.db import db
from app.common.presentation import present_user_datetime
from app.integrations.compatibility import get_profile
from app.models import AlertmanagerInstance, Cluster, PrometheusInstance
from app.models.integration import IntegrationBinding, IntegrationInstance, KubernetesConnection
from app.models.integration_runtime import IntegrationRuntimeObservation
from app.prometheus.repository import resolve_instance_for_cluster


def safe_endpoint(value: str | None) -> str:
    if not value:
        return 'Not configured'
    parsed = urlsplit(value)
    host = parsed.hostname or 'configured endpoint'
    port = f':{parsed.port}' if parsed.port else ''
    path = parsed.path.rstrip('/')
    return f'{parsed.scheme or "http"}://{host}{port}{path}'


def _alertmanager_for_cluster(cluster_id: str):
    from app.alertmanager.resolver import resolve_alertmanager_sources

    resolution = resolve_alertmanager_sources(scope_type='kubernetes_cluster', scope_key=cluster_id)
    selected = resolution.selected
    return selected.instance if selected else None


def build_rows() -> list[dict[str, Any]]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        rows.append(_row('prometheus', 'Prometheus', cluster, resolve_instance_for_cluster(cluster.id)))
        rows.append(_row('alertmanager', 'Alertmanager', cluster, _alertmanager_for_cluster(cluster.id)))
    return rows


def build_integrations_overview(
    *,
    provider: str = "",
    health: str = "",
    readiness: str = "",
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    rows = build_rows()
    prometheus_rows = [row for row in rows if row['key'] == 'prometheus']
    alertmanager_instances = AlertmanagerInstance.query.all()
    kubernetes_connections = KubernetesConnection.query.all()
    total = len(kubernetes_connections) + len(prometheus_rows) + len(alertmanager_instances)
    configured = len(kubernetes_connections) + sum(1 for row in prometheus_rows if row['configured']) + sum(
        1 for instance in alertmanager_instances if instance.endpoint
    )
    ready = sum(1 for connection in kubernetes_connections if connection.readiness_status == 'ready') + sum(1 for row in prometheus_rows if row['readiness'] == 'ready') + sum(
        1 for instance in alertmanager_instances if instance.readiness_status == 'ready'
    )
    blocked = sum(1 for connection in kubernetes_connections if connection.readiness_status == 'blocked') + sum(1 for row in prometheus_rows if row['readiness'] == 'blocked') + sum(
        1 for instance in alertmanager_instances if instance.readiness_status == 'blocked'
    )
    stats = {
        'total': total,
        'configured': configured,
        'ready': ready,
        'attention': max(configured - ready, 0),
        'blocked': blocked,
    }
    runtime_rows = _runtime_overview_rows()
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
    return {
        'rows': rows,
        'stats': stats,
        'catalog': _catalog(rows),
        'coverage': _coverage(rows),
        'runtime_rows': page_rows,
        'runtime_stats': runtime_stats,
        'runtime_pagination': runtime_pagination,
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
            {'value': 'not_observed', 'label': 'Not observed'},
        ],
        'runtime_readiness_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'degraded', 'label': 'Degraded'},
            {'value': 'blocked', 'label': 'Blocked'},
            {'value': 'validation_required', 'label': 'Validation required'},
        ],
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
        prometheus = resolve_instance_for_cluster(cluster.id)
        rows.append({
            'connection_id': connection.id,
            'integration_instance_id': connection.integration_instance_id,
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'environment': get_environment_label(cluster.environment),
            'server': connection.server or cluster.server or 'Not discovered',
            'readiness': connection.readiness_status or cluster.kubernetes_readiness_status or 'validation_required',
            'compatibility_profile': connection.compatibility_profile or cluster.kubernetes_compatibility_profile,
            'version': cluster.kubernetes_version,
            'binding_count': binding_count,
            'prometheus_instance_id': prometheus.id if prometheus else None,
            'prometheus_name': prometheus.name if prometheus else None,
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
    from app.integrations.runtime.kubernetes_adapter import runtime_adapter
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
    state = runtime_adapter.get_state(connection)
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
        'capability_scope': next((binding.capability_scope or [] for binding in connection.integration_instance.bindings if binding.asset_type == 'kubernetes_cluster' and binding.asset_key == cluster.id), []),
    }

def build_prometheus_page(
    *,
    compatibility: str = "",
    environment: str = "",
    readiness: str = "",
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    clusters_by_id = {cluster.id: cluster for cluster in Cluster.query.all()}
    all_rows: list[dict[str, Any]] = []
    covered_cluster_ids: set[str] = set()
    for instance in PrometheusInstance.query.order_by(PrometheusInstance.name.asc()).all():
        bindings = [binding for binding in instance.bindings if binding.enabled and binding.scope_type == 'kubernetes_cluster']
        cluster_ids = [binding.scope_key for binding in bindings]
        covered_cluster_ids.update(cluster_ids)
        bound_clusters = [clusters_by_id[key] for key in cluster_ids if key in clusters_by_id]
        environments = sorted({cluster.environment for cluster in bound_clusters if cluster.environment})
        readiness_value = instance.readiness_status or 'validation_required'
        compatibility_value = instance.compatibility_status or 'validation_required'
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
        })

    filtered = all_rows
    if compatibility:
        filtered = [row for row in filtered if row['compatibility'] == compatibility]
    if environment:
        filtered = [row for row in filtered if environment in row['environments']]
    if readiness:
        filtered = [row for row in filtered if row['readiness'] == readiness]
    page_rows, pagination = _paginate(filtered, page=page, per_page=per_page)
    uncovered = [cluster for cluster in clusters_by_id.values() if cluster.id not in covered_cluster_ids]
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
        'uncovered_clusters': sorted(uncovered, key=lambda cluster: cluster.name.lower()),
        'selected_compatibility': compatibility,
        'selected_environment': environment,
        'selected_readiness': readiness,
        'compatibility_options': _ordered_status_options(all_rows, 'compatibility', ['compatible', 'compatible_with_warnings', 'capability_mismatch', 'unsupported_version', 'version_unknown', 'validation_required']),
        'environment_options': [
            {'value': value, 'label': get_environment_label(value)}
            for value in sorted({value for row in all_rows for value in row['environments']}, key=lambda item: get_environment_label(item).lower())
        ],
        'readiness_options': _ordered_status_options(all_rows, 'readiness', ['ready', 'degraded', 'blocked', 'validation_required']),
    }


def build_alertmanager_page(
    *,
    query: str = '',
    readiness: str = '',
    deployment_type: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    from app.alertmanager.presentation import build_inventory_context

    return build_inventory_context(
        query=query,
        readiness=readiness,
        deployment_type=deployment_type,
        page=page,
        per_page=per_page,
    )



def _coverage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prometheus_rows = [row for row in rows if row['key'] == 'prometheus']
    alertmanager_instances = AlertmanagerInstance.query.all()
    observability_total = len(prometheus_rows) + len(alertmanager_instances)
    observability_configured = sum(1 for row in prometheus_rows if row['configured']) + sum(
        1 for instance in alertmanager_instances if instance.endpoint
    )
    observability_ready = sum(1 for row in prometheus_rows if row['readiness'] == 'ready') + sum(
        1 for instance in alertmanager_instances if instance.readiness_status == 'ready'
    )
    return [
        {
            'key': 'observability',
            'label': 'Observability',
            'icon': 'activity',
            'configured': observability_configured,
            'ready': observability_ready,
            'total': observability_total,
        },
        {'key': 'storage', 'label': 'Storage', 'icon': 'database', 'configured': 0, 'ready': 0, 'total': 0},
        {'key': 'security', 'label': 'Security', 'icon': 'shield-check', 'configured': 0, 'ready': 0, 'total': 0},
    ]


def _catalog(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configured_prometheus = sum(1 for row in rows if row['key'] == 'prometheus' and row['configured'])
    configured_alertmanager = AlertmanagerInstance.query.filter(AlertmanagerInstance.endpoint != '').count()
    configured_kubernetes = KubernetesConnection.query.count()
    return [
        {
            'key': 'kubernetes',
            'name': 'Kubernetes',
            'category': 'Compute & Infrastructure',
            'icon': 'boxes',
            'availability': 'available',
            'configured': configured_kubernetes,
            'description': 'Canonical Kubernetes API connections, asset identity, discovery, readiness, and operational access.',
        },
        {
            'key': 'prometheus',
            'name': 'Prometheus',
            'category': 'Observability',
            'icon': 'activity',
            'availability': 'available',
            'configured': configured_prometheus,
            'description': 'Metrics collection and versioned PromQL validation for connected infrastructure assets.',
        },
        {
            'key': 'alertmanager',
            'name': 'Alertmanager',
            'category': 'Observability',
            'icon': 'siren',
            'availability': 'available',
            'configured': configured_alertmanager,
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

def _stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'total': len(rows),
        'configured': sum(1 for row in rows if row['configured']),
        'ready': sum(1 for row in rows if row['readiness'] == 'ready'),
        'attention': sum(1 for row in rows if row['configured'] and row['readiness'] != 'ready'),
        'blocked': sum(1 for row in rows if row['readiness'] == 'blocked'),
    }


def _row(key: str, name: str, cluster: Cluster, config: object | None) -> dict[str, Any]:
    configured = bool(config and getattr(config, 'endpoint', None))
    profile_key = getattr(config, 'compatibility_profile', None) if config else None
    endpoint_product = (
        getattr(config, 'endpoint_product', None)
        if key == 'prometheus' and config
        else key
    ) or key
    profile = get_profile(endpoint_product, profile_key)
    return {
        'key': key,
        'name': name,
        'category': 'Observability',
        'cluster': cluster,
        'environment': cluster.environment,
        'environment_label': get_environment_label(cluster.environment),
        'configured': configured,
        'endpoint': safe_endpoint(getattr(config, 'endpoint', None) if config else None),
        'endpoint_product': endpoint_product,
        'version': getattr(config, 'detected_version', None) if config else None,
        'compatibility': (getattr(config, 'compatibility_status', None) if config else None) or ('validation_required' if configured else 'not_configured'),
        'readiness': (getattr(config, 'readiness_status', None) if config else None) or ('validation_required' if configured else 'not_configured'),
        'profile': profile_key,
        'profile_support': profile.support_level if profile else None,
        'validated_at': getattr(config, 'last_validated_at', None) if config else None,
        'message': getattr(config, 'validation_message', None) if config else None,
        'query_profile': getattr(config, 'query_profile', None) if key == 'prometheus' and config else None,
        'version_detection_mode': getattr(config, 'version_detection_mode', 'automatic') if key == 'prometheus' and config else None,
        'source_prometheus_major': getattr(config, 'source_prometheus_major', None) if key == 'prometheus' and config else None,
        'query_status': getattr(config, 'query_validation_status', None) if key == 'prometheus' and config else None,
        'retention': getattr(config, 'retention_validation_summary', None) if key == 'prometheus' and config else None,
    }


def _filter_prometheus_rows(
    rows: list[dict[str, Any]],
    *,
    compatibility: str,
    environment: str,
    readiness: str,
) -> list[dict[str, Any]]:
    filtered = rows
    if compatibility:
        filtered = [row for row in filtered if row['compatibility'] == compatibility]
    if environment:
        filtered = [row for row in filtered if row['environment'] == environment]
    if readiness:
        filtered = [row for row in filtered if row['readiness'] == readiness]
    return filtered


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


def _runtime_overview_rows() -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], IntegrationRuntimeObservation] = {}
    observations = IntegrationRuntimeObservation.query.order_by(
        IntegrationRuntimeObservation.observed_at.desc(),
        IntegrationRuntimeObservation.id.desc(),
    ).all()
    for observation in observations:
        latest.setdefault((observation.provider, observation.instance_id), observation)

    rows: list[dict[str, Any]] = []
    for connection in KubernetesConnection.query.join(Cluster).order_by(Cluster.created_at.asc(), Cluster.id.asc()).all():
        cluster = connection.cluster
        canonical = db.session.get(IntegrationInstance, connection.integration_instance_id)
        observation = latest.get(('kubernetes', str(connection.id)))
        observed_at = observation.observed_at if observation else (connection.last_validated_at or cluster.kubernetes_last_validated_at)
        rows.append({
            'provider': 'kubernetes',
            'provider_label': 'Kubernetes',
            'instance_id': str(connection.id),
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
            'detail_endpoint': 'cluster.edit_cluster',
            'detail_kwargs': {'cluster_id': cluster.id},
        })

    for instance in PrometheusInstance.query.order_by(PrometheusInstance.name.asc()).all():
        observation = latest.get(('prometheus', str(instance.id)))
        assessments = ((instance.capabilities or {}).get('assessments') or [])
        attention = sum(1 for item in assessments if item.get('status') != 'available')
        observed_at = observation.observed_at if observation else instance.last_checked_at
        latency_ms = observation.latency_ms if observation else instance.last_response_time_ms
        enabled_bindings = [binding for binding in instance.bindings if binding.enabled]
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
            'detail_endpoint': 'prometheus.instance_detail',
            'detail_kwargs': {'instance_id': instance.id},
        })

    for instance in AlertmanagerInstance.query.order_by(AlertmanagerInstance.name.asc()).all():
        observation = latest.get(('alertmanager', str(instance.id)))
        observed_at = observation.observed_at if observation else instance.last_checked_at
        latency_ms = observation.latency_ms if observation else instance.last_response_time_ms
        capability_attention = 0 if instance.capabilities else 1
        rows.append({
            'provider': 'alertmanager',
            'provider_label': 'Alertmanager',
            'instance_id': str(instance.id),
            'instance_name': instance.name,
            'scope_label': f'{len(instance.bindings)} asset binding(s)',
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
            'detail_endpoint': 'alertmanager.instance_detail',
            'detail_kwargs': {'instance_id': instance.id},
        })

    health_order = {'unhealthy': 0, 'degraded': 1, 'not_observed': 2, 'healthy': 3}
    rows.sort(key=lambda row: (health_order.get(row['health_status'], 2), row['provider_label'], row['instance_name'].lower()))
    return rows
