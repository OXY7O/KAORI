from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from app.cluster.constants import get_environment_label
from app.common.presentation import present_user_datetime
from app.integrations.compatibility import get_profile
from app.models import AlertmanagerConfig, AlertmanagerInstance, Cluster, PrometheusConfig
from app.models.integration_runtime import IntegrationRuntimeObservation


def safe_endpoint(value: str | None) -> str:
    if not value:
        return 'Not configured'
    parsed = urlsplit(value)
    host = parsed.hostname or 'configured endpoint'
    port = f':{parsed.port}' if parsed.port else ''
    path = parsed.path.rstrip('/')
    return f'{parsed.scheme or "http"}://{host}{port}{path}'


def build_rows() -> list[dict[str, Any]]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    prometheus = {item.cluster_id: item for item in PrometheusConfig.query.all()}
    alertmanager = {item.cluster_id: item for item in AlertmanagerConfig.query.all()}
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        rows.append(_row('prometheus', 'Prometheus', cluster, prometheus.get(cluster.id)))
        rows.append(_row('alertmanager', 'Alertmanager', cluster, alertmanager.get(cluster.id)))
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
    total = len(prometheus_rows) + len(alertmanager_instances)
    configured = sum(1 for row in prometheus_rows if row['configured']) + sum(
        1 for instance in alertmanager_instances if instance.endpoint
    )
    ready = sum(1 for row in prometheus_rows if row['readiness'] == 'ready') + sum(
        1 for instance in alertmanager_instances if instance.readiness_status == 'ready'
    )
    blocked = sum(1 for row in prometheus_rows if row['readiness'] == 'blocked') + sum(
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


def build_prometheus_page(
    *,
    compatibility: str = "",
    environment: str = "",
    readiness: str = "",
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    all_rows = [row for row in build_rows() if row['key'] == 'prometheus']
    rows = _filter_prometheus_rows(
        all_rows,
        compatibility=compatibility,
        environment=environment,
        readiness=readiness,
    )
    page_rows, pagination = _paginate(rows, page=page, per_page=per_page)
    return {
        'rows': page_rows,
        'stats': _stats(all_rows),
        'pagination': pagination,
        'selected_compatibility': compatibility,
        'selected_environment': environment,
        'selected_readiness': readiness,
        'compatibility_options': _ordered_status_options(all_rows, 'compatibility', ['compatible', 'compatible_with_warnings', 'capability_mismatch', 'unsupported_version', 'version_unknown', 'validation_required', 'not_configured']),
        'environment_options': [
            {'value': value, 'label': get_environment_label(value)}
            for value in sorted({row['environment'] for row in all_rows if row['environment']}, key=lambda item: get_environment_label(item).lower())
        ],
        'readiness_options': _ordered_status_options(all_rows, 'readiness', ['ready', 'degraded', 'blocked', 'validation_required', 'not_configured']),
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
    return [
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
    for config in PrometheusConfig.query.join(Cluster).order_by(Cluster.name.asc()).all():
        observation = latest.get(('prometheus', str(config.id)))
        assessments = ((config.capabilities or {}).get('assessments') or [])
        attention = sum(1 for item in assessments if item.get('status') != 'available')
        observed_at = observation.observed_at if observation else config.last_checked_at
        latency_ms = observation.latency_ms if observation else config.last_response_time_ms
        rows.append({
            'provider': 'prometheus',
            'provider_label': 'Prometheus / Thanos',
            'instance_id': str(config.id),
            'instance_name': f'{config.cluster.name} metrics',
            'scope_label': config.cluster.name,
            'endpoint_product': (config.endpoint_product or 'prometheus').replace('_', ' ').title(),
            'health_status': observation.health_status if observation else 'not_observed',
            'health_score': observation.health_score if observation else None,
            'readiness': config.readiness_status or 'validation_required',
            'observed_at': observed_at,
            'observed_at_display': present_user_datetime(observed_at, empty='Not observed'),
            'latency_ms': latency_ms,
            'latency_display': f'{latency_ms} ms' if latency_ms is not None else None,
            'capability_profile': config.capability_profile or config.query_profile,
            'capability_attention': attention,
            'capability_attention_display': (
                f'{attention} item needs attention' if attention == 1 else f'{attention} items need attention'
            ),
            'message': (observation.message if observation else None) or config.validation_message or config.last_error,
            'detail_endpoint': 'prometheus.configuration',
            'detail_kwargs': {'cluster_id': config.cluster_id},
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
