from __future__ import annotations

from typing import Any

from app.models import AlertmanagerConfig, Cluster, PrometheusConfig


def build_integrations_overview() -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    rows: list[dict[str, Any]] = []

    for cluster in clusters:
        prometheus = PrometheusConfig.query.filter_by(cluster_id=cluster.id).first()
        alertmanager = AlertmanagerConfig.query.filter_by(cluster_id=cluster.id).first()
        rows.extend(
            (
                _row('Prometheus', 'Observability', cluster, prometheus),
                _row('Alertmanager', 'Observability', cluster, alertmanager),
            )
        )

    configured = sum(1 for row in rows if row['configured'])
    ready = sum(1 for row in rows if row['readiness'] == 'ready')
    attention = sum(1 for row in rows if row['configured'] and row['readiness'] != 'ready')
    return {
        'rows': rows,
        'stats': {
            'configured': configured,
            'ready': ready,
            'attention': attention,
        },
    }


def _row(name: str, category: str, cluster: Cluster, config: object | None) -> dict[str, Any]:
    configured = bool(config and getattr(config, 'endpoint', None))
    return {
        'name': name,
        'category': category,
        'cluster': cluster,
        'configured': configured,
        'version': getattr(config, 'detected_version', None) if config else None,
        'compatibility': getattr(config, 'compatibility_status', None) if config else None,
        'readiness': getattr(config, 'readiness_status', None) if config else None,
        'profile': getattr(config, 'compatibility_profile', None) if config else None,
        'validated_at': getattr(config, 'last_validated_at', None) if config else None,
    }
