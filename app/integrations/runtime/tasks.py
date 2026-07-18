from __future__ import annotations

import logging

from celery import shared_task

from app.alertmanager.runtime_adapter import runtime_adapter as alertmanager_runtime_adapter
from app.extensions import db
from app.models.alertmanager import AlertmanagerInstance
from app.models.prometheus import PrometheusConfig
from app.prometheus.runtime_adapter import runtime_adapter as prometheus_runtime_adapter

from .monitoring import refresh_and_record

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='app.integrations.runtime.tasks.refresh_integration_runtime', acks_late=True, reject_on_worker_lost=True)
def refresh_integration_runtime(self) -> dict[str, object]:
    results: dict[str, object] = {'refreshed': 0, 'failed': 0, 'providers': {}}
    providers = (
        ('alertmanager', alertmanager_runtime_adapter, AlertmanagerInstance.query.filter_by(enabled=True).order_by(AlertmanagerInstance.id.asc()).all()),
        ('prometheus', prometheus_runtime_adapter, PrometheusConfig.query.order_by(PrometheusConfig.id.asc()).all()),
    )
    for provider, adapter, instances in providers:
        provider_result = {'refreshed': 0, 'failed': 0, 'instances': []}
        for instance in instances:
            try:
                _, state, _ = refresh_and_record(adapter, instance, trigger_type='scheduled')
                provider_result['refreshed'] += 1
                results['refreshed'] += 1
                provider_result['instances'].append({'id': instance.id, 'health': state.health.status, 'score': state.health.score})
            except Exception as exc:
                db.session.rollback()
                logger.exception('Runtime refresh failed for %s instance %s.', provider, instance.id)
                provider_result['failed'] += 1
                results['failed'] += 1
                provider_result['instances'].append({'id': instance.id, 'error': str(exc)[:300]})
        results['providers'][provider] = provider_result
    return results
