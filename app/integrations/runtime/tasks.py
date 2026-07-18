from __future__ import annotations
import logging
from celery import shared_task
from app.extensions import db
from app.models.alertmanager import AlertmanagerInstance
from app.alertmanager.runtime_adapter import runtime_adapter
from .monitoring import refresh_and_record
logger = logging.getLogger(__name__)

@shared_task(bind=True, name='app.integrations.runtime.tasks.refresh_integration_runtime', acks_late=True, reject_on_worker_lost=True)
def refresh_integration_runtime(self) -> dict[str, object]:
    results: dict[str, object] = {'provider': 'alertmanager', 'refreshed': 0, 'failed': 0, 'instances': []}
    for instance in AlertmanagerInstance.query.filter_by(enabled=True).order_by(AlertmanagerInstance.id.asc()).all():
        try:
            _, state, _ = refresh_and_record(runtime_adapter, instance, trigger_type='scheduled')
            results['refreshed'] += 1
            results['instances'].append({'id': instance.id, 'health': state.health.status, 'score': state.health.score})
        except Exception as exc:
            db.session.rollback(); logger.exception('Runtime refresh failed for Alertmanager instance %s.', instance.id)
            results['failed'] += 1
            results['instances'].append({'id': instance.id, 'error': str(exc)[:300]})
    return results
