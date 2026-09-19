from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

_HEALTHY_STATES = {'healthy'}
_KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'
_INVENTORY_JOB_KEY = 'kubernetes.inventory.sync'
_TLS_CERTIFICATE_JOB_KEY = 'governance.tls_certificates.sync'
_ANALYTICS_JOB_KEY = 'analytics.materialize'


class RecoveryDispatchResult(TypedDict):
    integration_type: str
    clusters: list[str]
    queued: int
    skipped: int


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


def _get_job_definition(job_key: str) -> Any:
    from app.platform_operations.jobs.registry import get_job_definition

    return get_job_definition(job_key)


def _dispatch_recovery_job(*, job_key: str, parameters: dict[str, Any]) -> bool:
    outcome = _get_job_definition(job_key).dispatch(
        requested_by_user_id=None,
        trigger_type='recovery',
        parameters=parameters,
    )
    return bool(outcome.accepted and outcome.created)


def _record_dispatch(result: RecoveryDispatchResult, *, created: bool) -> None:
    result['queued'] += int(created)
    result['skipped'] += int(not created)


def enqueue_recovery_work(*, integration_type: str, instance: Any) -> RecoveryDispatchResult:
    """Queue focused data refresh after a provider transitions back to healthy.

    Recovery dispatch is best-effort. A failed enqueue must never turn a healthy
    runtime refresh back into a failed runtime observation. Registered job
    definitions remain the canonical dispatch boundary, so Integration Runtime
    does not import Inventory, Governance, or Analytics implementations directly.
    """
    cluster_ids = _bound_cluster_ids(instance)
    result: RecoveryDispatchResult = {
        'integration_type': integration_type,
        'clusters': cluster_ids,
        'queued': 0,
        'skipped': 0,
    }
    if not cluster_ids:
        return result

    if integration_type == 'container_orchestrator':
        requests = (
            (_INVENTORY_JOB_KEY, 'inventory'),
            (_TLS_CERTIFICATE_JOB_KEY, 'TLS certificate'),
        )
        for cluster_id in cluster_ids:
            for job_key, label in requests:
                try:
                    created = _dispatch_recovery_job(
                        job_key=job_key,
                        parameters={'cluster_id': cluster_id},
                    )
                except Exception:
                    logger.exception(
                        'Could not queue recovery %s sync for cluster %s.',
                        label,
                        cluster_id,
                    )
                    result['skipped'] += 1
                else:
                    _record_dispatch(result, created=created)
        return result

    if integration_type not in {'metrics_source', 'alert_source'}:
        return result

    requests = (
        ('dashboard.kubernetes.alerts', {}),
        ('analytics.alerts', {'source': 'auto'}),
    )
    for cluster_id in cluster_ids:
        for dataset_key, snapshot_parameters in requests:
            try:
                created = _dispatch_recovery_job(
                    job_key=_ANALYTICS_JOB_KEY,
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
                result['skipped'] += 1
            else:
                _record_dispatch(result, created=created)
    return result
