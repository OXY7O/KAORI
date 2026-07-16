from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

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


def build_prometheus_page() -> dict[str, Any]:
    rows = [row for row in build_rows() if row['key'] == 'prometheus']
    return {'rows': rows, 'stats': _stats(rows)}


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
    profile = get_profile(key, profile_key)
    return {
        'key': key,
        'name': name,
        'category': 'Observability',
        'cluster': cluster,
        'configured': configured,
        'endpoint': safe_endpoint(getattr(config, 'endpoint', None) if config else None),
        'version': getattr(config, 'detected_version', None) if config else None,
        'compatibility': (getattr(config, 'compatibility_status', None) if config else None) or ('validation_required' if configured else 'not_configured'),
        'readiness': (getattr(config, 'readiness_status', None) if config else None) or ('validation_required' if configured else 'not_configured'),
        'profile': profile_key,
        'profile_support': profile.support_level if profile else None,
        'validated_at': getattr(config, 'last_validated_at', None) if config else None,
        'message': getattr(config, 'validation_message', None) if config else None,
        'query_profile': getattr(config, 'query_profile', None) if key == 'prometheus' and config else None,
        'query_status': getattr(config, 'query_validation_status', None) if key == 'prometheus' and config else None,
        'retention': getattr(config, 'retention_validation_summary', None) if key == 'prometheus' and config else None,
    }
