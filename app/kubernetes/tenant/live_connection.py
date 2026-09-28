from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.common.presentation import present_user_datetime
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.models import Cluster
from app.models.kubernetes import KubernetesConnection


def get_live_tenant_connection_context() -> dict[str, Any]:
    """Probe Kubernetes API reachability for Tenant workflows that use live provider state."""

    clusters = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .order_by(Cluster.name.asc(), Cluster.id.asc())
        .all()
    )
    checked_at = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        connection = cluster.kubernetes_connection
        try:
            version = runtime_adapter.build_client(cluster).version_api().get_code(_request_timeout=3)
        except Exception:
            rows.append({
                'cluster_id': str(cluster.id),
                'cluster_name': cluster.name,
                'environment': cluster.environment,
                'reachable': False,
                'version': connection.detected_version if connection is not None else None,
                'message': 'Live Kubernetes API probe failed.',
            })
            continue
        rows.append({
            'cluster_id': str(cluster.id),
            'cluster_name': cluster.name,
            'environment': cluster.environment,
            'reachable': True,
            'version': str(getattr(version, 'git_version', None) or connection.detected_version or 'Unknown'),
            'message': 'Live Kubernetes API reachable.',
        })

    total = len(rows)
    reachable = sum(1 for row in rows if row['reachable'])
    failures = total - reachable
    if total == 0:
        status, tone = 'Unavailable', 'warning'
        description = 'No canonical Kubernetes connection is registered for live Tenant provider operations.'
    elif failures == 0:
        status, tone = 'Connected', 'normal'
        description = 'Live Kubernetes API reachability is available for provider-backed Tenant operations.'
    elif reachable:
        status, tone = 'Partial', 'warning'
        description = 'Some Kubernetes clusters are unreachable; provider-backed Tenant operations fail closed per target.'
    else:
        status, tone = 'Unavailable', 'critical'
        description = 'Kubernetes API is unreachable for the current Tenant provider scope.'

    return {
        'tenant_live_connection': {
            'status': status,
            'tone': tone,
            'description': description,
            'source_label': 'Live Kubernetes API',
            'checked_at_label': present_user_datetime(checked_at),
            'scope_label': f'{reachable} / {total} Clusters',
            'coverage_label': f'{reachable} Reachable',
            'coverage_supporting': 'Live API reachability',
            'coverage_tone': 'normal' if failures == 0 and total else 'warning',
            'exception_label': 'No Exceptions' if failures == 0 else f'{failures} Connection Exception' + ('' if failures == 1 else 's'),
            'exceptions_tone': 'normal' if failures == 0 else 'warning',
            'rows': rows,
        }
    }
