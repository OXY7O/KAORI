from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from app.cluster.constants import get_environment_label
from app.integrations.compatibility import get_profile
from app.models import AlertmanagerConfig, Cluster, PrometheusConfig


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


def build_integrations_overview() -> dict[str, Any]:
    rows = build_rows()
    stats = _stats(rows)
    return {
        'rows': rows,
        'stats': stats,
        'catalog': _catalog(rows),
        'coverage': _coverage(rows),
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


def build_alertmanager_page() -> dict[str, Any]:
    rows = [row for row in build_rows() if row['key'] == 'alertmanager']
    return {'rows': rows, 'stats': _stats(rows)}



def _coverage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observability = [row for row in rows if row['category'] == 'Observability']
    return [
        {'key': 'observability', 'label': 'Observability', 'icon': 'activity',
         'configured': sum(1 for row in observability if row['configured']),
         'ready': sum(1 for row in observability if row['readiness'] == 'ready'),
         'total': len(observability)},
        {'key': 'storage', 'label': 'Storage', 'icon': 'database', 'configured': 0, 'ready': 0, 'total': 0},
        {'key': 'security', 'label': 'Security', 'icon': 'shield-check', 'configured': 0, 'ready': 0, 'total': 0},
    ]


def _catalog(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configured_by_key = {
        key: sum(1 for row in rows if row['key'] == key and row['configured'])
        for key in ('prometheus', 'alertmanager')
    }
    return [
        {'key': 'prometheus', 'name': 'Prometheus', 'category': 'Observability', 'icon': 'activity',
         'availability': 'available', 'configured': configured_by_key['prometheus'],
         'description': 'Metrics collection and versioned PromQL validation for connected infrastructure assets.'},
        {'key': 'alertmanager', 'name': 'Alertmanager', 'category': 'Observability', 'icon': 'siren',
         'availability': 'available', 'configured': configured_by_key['alertmanager'],
         'description': 'Alert retrieval, silence capability, routing posture, and API compatibility validation.'},
        {'key': 's3', 'name': 'S3-compatible Storage', 'category': 'Storage', 'icon': 'database',
         'availability': 'planned', 'configured': 0,
         'description': 'Reusable object storage for reports, archives, and long-term operational evidence.'},
        {'key': 'vault', 'name': 'Vault', 'category': 'Security', 'icon': 'key-round',
         'availability': 'planned', 'configured': 0,
         'description': 'External secret and credential management with controlled access and auditability.'},
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
        'capability_profile': getattr(config, 'capability_profile', None) if key == 'alertmanager' and config else None,
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
