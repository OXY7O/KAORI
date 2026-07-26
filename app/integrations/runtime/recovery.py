from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_HEALTHY_STATES = {'healthy'}
_KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'


def latest_runtime_health(integration_instance_id: int | None) -> str | None:
    if integration_instance_id is None:
        return None
    from app.models.runtime import IntegrationRuntimeObservation

    row = (
        IntegrationRuntimeObservation.query.filter_by(
            integration_instance_id=integration_instance_id,
        )
        .order_by(
            IntegrationRuntimeObservation.observed_at.desc(),
            IntegrationRuntimeObservation.id.desc(),
        )
        .first()
    )
    return str(row.health_status).lower() if row is not None and row.health_status else None


def is_runtime_recovery(previous_status: str | None, current_status: str | None) -> bool:
    previous = str(previous_status or '').lower()
    current = str(current_status or '').lower()
    return bool(previous) and previous not in _HEALTHY_STATES and current in _HEALTHY_STATES


def _bound_cluster_ids(instance: Any) -> list[str]:
    direct_cluster_id = str(getattr(instance, 'cluster_id', '') or '').strip()
    if direct_cluster_id:
        return [direct_cluster_id]

    identity = getattr(instance, 'integration_instance', None)
    bindings = getattr(identity, 'bindings', None) or []
    return sorted(
        {
            str(binding.asset_key)
            for binding in bindings
            if getattr(binding, 'enabled', False)
            and getattr(binding, 'asset_type', None) == _KUBERNETES_CLUSTER_SCOPE
            and str(getattr(binding, 'asset_key', '') or '').strip()
        }
    )


def enqueue_recovery_work(*, provider_type: str, instance: Any) -> dict[str, object]:
    """Queue focused data refresh after a provider transitions back to healthy.

    Recovery dispatch is best-effort. A failed enqueue must never turn a healthy
    runtime refresh back into a failed runtime observation.
    """
    cluster_ids = _bound_cluster_ids(instance)
    result: dict[str, object] = {'provider_type': provider_type, 'clusters': cluster_ids, 'queued': 0, 'skipped': 0}
    if not cluster_ids:
        return result

    if provider_type == 'kubernetes':
        from app.cluster.sync_jobs import enqueue_cluster_inventory_sync
        from app.models.cluster import Cluster

        for cluster_id in cluster_ids:
            cluster = Cluster.query.get(cluster_id)
            if cluster is None:
                result['skipped'] = int(result['skipped']) + 1
                continue
            try:
                _, created = enqueue_cluster_inventory_sync(
                    cluster=cluster,
                    requested_by_user_id=None,
                    trigger_type='recovery',
                )
            except Exception:
                logger.exception('Could not queue recovery inventory sync for cluster %s.', cluster_id)
                result['skipped'] = int(result['skipped']) + 1
            else:
                result['queued'] = int(result['queued']) + int(created)
                result['skipped'] = int(result['skipped']) + int(not created)
        return result

    if provider_type not in {'prometheus', 'alertmanager'}:
        return result

    from app.analytics.job_adapter import dispatch_analytics_materialization

    requests = (
        ('dashboard.kubernetes.alerts', {}),
        ('analytics.alerts', {'source': 'auto'}),
    )
    for cluster_id in cluster_ids:
        for dataset_key, snapshot_parameters in requests:
            try:
                outcome = dispatch_analytics_materialization(
                    requested_by_user_id=None,
                    trigger_type='recovery',
                    parameters={
                        'cluster_id': cluster_id,
                        'dataset_key': dataset_key,
                        'snapshot_parameters': snapshot_parameters,
                    },
                )
            except Exception:
                logger.exception(
                    'Could not queue recovery analytics refresh for %s on cluster %s.',
                    dataset_key,
                    cluster_id,
                )
                result['skipped'] = int(result['skipped']) + 1
            else:
                result['queued'] = int(result['queued']) + int(outcome.created)
                result['skipped'] = int(result['skipped']) + int(not outcome.created)
    return result
