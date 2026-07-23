from __future__ import annotations

import logging
from typing import Any

from app.integrations.validation.tasks import enqueue_runtime_refresh
from app.models.alertmanager import AlertmanagerInstance
from app.models.kubernetes import KubernetesConnection
from app.models.prometheus import PrometheusInstance

from .refresh import refresh_runtime
from .repository import persist_runtime_state

logger = logging.getLogger(__name__)

__all__ = ['dispatch_integration_runtime_refresh', 'refresh_and_record']


def _canonical_instance_id(instance: Any) -> int | None:
    value = getattr(instance, 'integration_instance_id', None)
    if value is not None:
        return int(value)
    connection = getattr(instance, 'kubernetes_connection', None)
    value = getattr(connection, 'integration_instance_id', None)
    return int(value) if value is not None else None


def refresh_and_record(adapter: Any, instance: Any, *, trigger_type: str = 'manual'):
    validation_result, state = refresh_runtime(adapter, instance)
    observation = persist_runtime_state(
        state,
        trigger_type=trigger_type,
        integration_instance_id=_canonical_instance_id(instance),
    )
    return validation_result, state, observation


def dispatch_integration_runtime_refresh() -> dict[str, object]:
    """Queue independent runtime refresh jobs for all enabled providers."""
    provider_ids = {
        'kubernetes': [
            row.id
            for row in KubernetesConnection.query.order_by(KubernetesConnection.id.asc()).all()
        ],
        'alertmanager': [
            row.id
            for row in AlertmanagerInstance.query.filter_by(enabled=True)
            .order_by(AlertmanagerInstance.id.asc())
            .all()
        ],
        'prometheus': [
            row.id
            for row in PrometheusInstance.query.filter_by(enabled=True)
            .order_by(PrometheusInstance.id.asc())
            .all()
        ],
    }
    result: dict[str, Any] = {'queued': 0, 'skipped': 0, 'providers': {}}
    for provider_type, instance_ids in provider_ids.items():
        provider_result: dict[str, Any] = {'queued': 0, 'skipped': 0, 'tasks': []}
        for instance_id in instance_ids:
            try:
                task_id = enqueue_runtime_refresh(
                    provider_type=provider_type,
                    instance_id=int(instance_id),
                )
            except Exception as exc:
                logger.exception(
                    'Could not enqueue runtime refresh for %s instance %s.',
                    provider_type,
                    instance_id,
                )
                provider_result['skipped'] += 1
                result['skipped'] += 1
                provider_result['tasks'].append(
                    {'instance_id': instance_id, 'error': str(exc)[:300]}
                )
                continue
            if task_id is None:
                provider_result['skipped'] += 1
                result['skipped'] += 1
                provider_result['tasks'].append(
                    {'instance_id': instance_id, 'status': 'already_active'}
                )
                continue
            provider_result['queued'] += 1
            result['queued'] += 1
            provider_result['tasks'].append(
                {'instance_id': instance_id, 'task_id': task_id}
            )
        result['providers'][provider_type] = provider_result
    return result
